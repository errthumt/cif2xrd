import math
import matplotlib.pyplot as plt
from matplotlib.transforms import ScaledTranslation

from cif2xrd.paramUtils import clean_parameters, parse_params, default_params #type:ignore

START = "start"
RAMP = "ramp"
DWELL = "dwell"



def crop_axes_to_content(ax, l_marg=0, r_marg=0, t_marg=0, b_marg=0, pad=2):
    """
    Remove whitespace by shrinking axis limits to tightly wrap
    all lines, text, and annotations on the Axes.
    pad is in display (pixel) units.
    """
    fig = ax.figure
    fig.canvas.draw()  # ensure all artists have valid extents

    # Collect all bounding boxes in display coords
    bboxes = []

    # Lines, markers, etc.
    for line in ax.lines:
        bboxes.append(line.get_window_extent())

    # Text objects (labels, annotations, etc.)
    for txt in ax.texts:
        bboxes.append(txt.get_window_extent(renderer=fig.canvas.get_renderer()))

    # Collections (e.g., patches, arrows)
    for coll in ax.collections:
        try:
            bboxes.append(coll.get_window_extent(fig.canvas.get_renderer()))
        except Exception:
            pass

    # Merge into a single bounding box
    if not bboxes:
        return  # nothing to crop

    from matplotlib.transforms import Bbox
    full = Bbox.union(bboxes)

    # Add padding in display units
    full = full.expanded((full.width + 2*pad)/full.width,
                        (full.height + 2*pad)/full.height)

    # Convert display → data coordinates
    inv = ax.transData.inverted()
    x0, y0 = inv.transform((full.x0, full.y0))
    x1, y1 = inv.transform((full.x1, full.y1))

    # Apply new limits
    ax.set_xlim(x0-l_marg, x1+r_marg)
    ax.set_ylim(y0-b_marg, y1+t_marg)


profile_defaults = {
    "start_temp": 25,
    "min_height": 6,
    "add_temps": [],
    "ramp_width": 4,
    "dwell_width": 6,
    "font_family": "Arial",
    "font_size": 35,
    "text_offset": 1,
    "line_width": 4,
    "l_marg": 1,
    "r_marg": 1,
    "t_marg": 1,
    "b_marg": 1,
}

sliders = {
    "min_height": ("Section Height", 1, 20),
    "ramp_width": ("Ramp Width", 1, 20),
    "dwell_width": ("Dwell Width", 1, 20),
    "font_size": ("Font Size", 1, 50),
    "text_offset": ("Text Offset", 0, 5),
    "line_width": ("Line Thickness", 1, 5),
    "l_marg": ("Left Margin", 1, 10),
    "r_marg": ("Right Margin", 1, 10),
    "t_marg": ("Top Margin", 1, 10),
    "b_marg": ("Bottom Margin", 1, 10),
}


class Profile:
    def __init__(self, **kwargs):
        # Load defaults
        for attr, default in profile_defaults.items():
            if isinstance(default, list):
                # avoid shared mutable defaults
                setattr(self, attr, default.copy())
            else:
                setattr(self, attr, default)

        self.sections = [None]
        self.notes = []
        self.is_quenched = False

        # Apply overrides
        self.update_params(**kwargs)


    def update_params(self, **kwargs):
        for key, value in kwargs.items():
            if key not in profile_defaults:
                raise ValueError(f"Unknown Profile parameter: '{key}'")

            # Avoid mutable default traps
            if key == "add_temps":
                value = list(value)

            setattr(self, key, value)

        # Rebuild font if either component changed
        self.font = [self.font_family, self.font_size]
        self.sections[0] = [START, self.start_temp]

    def ramp(self,new_temp,time_note=""):
        self.sections.append([RAMP,new_temp])
        self.notes.append([time_note,""])

    def dwell(self, time_note=""):
        current_temp = self.sections[-1][1]
        self.sections.append([DWELL,current_temp])
        self.notes.append([f'{int(current_temp)}°C',time_note])

    def quench(self,note):
        self.is_quenched = note

    def get_coords(self, ax):
        """
        Compute coordinates for each section, using Matplotlib text measurement
        in *data units*, based on the actual axis used in the final plot.
        """

        fig = ax.figure

        # --- Build unique temperature list ---
        unique_temps = self.add_temps.copy()

        for type, temp in self.sections:
            if temp not in unique_temps:
                unique_temps.append(temp)
            unique_temps.sort()

        # --- Ensure renderer exists ---
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # --- Text width measurement using THIS axis ---
        def text_width_data_units(text):
            """
            Measure text width in data units using the actual axis transforms.
            """
            # Create invisible text on the real axis
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            t = ax.text(
                xlim[1]/2, ylim[1]/2, text,
                fontsize=self.font[1],
                family=self.font[0],
                transform=ax.transData,
                visible=True
            )

            # Must draw so bbox is valid
            fig.canvas.draw()

            bbox = t.get_window_extent(renderer=renderer)
            w_px = bbox.width
            #print(w_px)

            # 1. Convert pixel offset to axis-fraction offset
            (x0_ax, _), (x1_ax, _) = ax.transAxes.inverted().transform(
                [(0, 0), (w_px, 0)]
            )

            # 2. Convert axis-fraction offset to data offset
            data_width = (x1_ax - x0_ax) * (ax.get_xlim()[1] - ax.get_xlim()[0])
            #print(x1_ax)
            #print(x0_ax)
            #print(ax.get_xlim()[1]-ax.get_xlim()[0])
            t.remove()
            return abs(data_width)

        # --- Compute text widths for each note pair ---
        text_widths = [0]  # first section has no notes
        for texts in self.notes:
            w = max(text_width_data_units(t) for t in texts)
            text_widths.append(w)

        # --- Compute coordinates ---
        coords = []
        current_x = 0
        last_temp = self.start_temp
        for (type, temp), t_width in zip(self.sections, text_widths):
            temp_index = unique_temps.index(temp)
            last_index = unique_temps.index(last_temp)
            last_temp = temp
            if type == RAMP:
                
                height_change = abs((temp_index-last_index)/2)
                orig_angle = math.atan(self.min_height * height_change / self.ramp_width)
                try:
                    text_angle = math.asin(self.min_height * height_change / t_width)
                except:
                    text_angle = 4
                angle = min(orig_angle, text_angle)
                #print(f'comparing {min_width} with {self.ramp_width}')
                current_x += self.min_height * height_change / math.tan(angle)

            elif type == DWELL:
                #print(f'comparing {t_width} with {self.dwell_width}')
                current_x += max(t_width, self.dwell_width)

            coords.append([current_x, unique_temps.index(temp) * self.min_height])

        #print(coords)
        return coords
    '''
    def plot(self):
        # --- Create figure and axis ---
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

        self.text_trans = ax.transData + ScaledTranslation(0, 0, ax.figure.dpi_scale_trans)

        fig.subplots_adjust(left=0,right=1,top=1,bottom=0)

        est_y = self.min_height*len(self.sections)
        ax.invert_yaxis()
        ax.set_xlim(0, est_y)
        ax.set_ylim(0, est_y)
        ax.autoscale(False)

        points = self.get_coords(ax)


        # Turn off axes for a clean canvas-like look
        ax.axis("off")

        fontsize = self.font[1]
        
        for i, ((x1, y1), (x2, y2)) in enumerate(zip(points, points[1:])):
            # Draw the line segment
            ax.plot([x1, x2], [y1, y2], color="black", linewidth=self.line_width)

            if i < len(self.notes):
                top_text, bottom_text = self.notes[i]

                # midpoint
                xm = (x1 + x2) / 2
                ym = (y1 + y2) / 2

                # angle
                dx = x2 - x1
                dy = y2 - y1
                angle_deg = math.degrees(math.atan2(dy, dx))

                # --- Compute a small perpendicular offset in data units ---
                # Normal vector (unit)
                nx = -dy
                ny = dx
                L = math.hypot(nx, ny)
                nx /= L
                ny /= L

                # Apply your offset
                off = self.text_offset

                # Top label position
                top_x = xm + nx * off
                top_y = ym + ny * off

                # Bottom label position
                bottom_x = xm - nx * off
                bottom_y = ym - ny * off

                # --- TOP LABEL ---
                ax.text(
                    top_x, top_y,
                    top_text,
                    ha="center", va="bottom",
                    rotation=angle_deg,
                    rotation_mode="anchor",
                    transform_rotates_text=True,
                    transform=ax.transData,
                    fontsize=fontsize,
                    family=self.font[0]
                )

                # --- BOTTOM LABEL ---
                ax.text(
                    bottom_x, bottom_y,
                    bottom_text,
                    ha="center", va="top",
                    rotation=angle_deg,
                    rotation_mode="anchor",
                    transform_rotates_text=True,
                    transform=ax.transData,
                    fontsize=fontsize,
                    family=self.font[0]
                )
            # ------------------------------------------------------------------
            # RAMP-END TEMPERATURE LABEL (if next section is NOT a dwell)
            # ------------------------------------------------------------------

            if self.sections[i+1][0] == RAMP:
                is_last = (i == len(self.sections) - 2)
                if is_last:
                    next_is_dwell = False
                else:
                    next_is_dwell = (not is_last and self.sections[i+2][0] == DWELL)

                if is_last or not next_is_dwell:
                    # temperature at end of this ramp
                    temp = self.sections[i+1][1]
                    label = f"{int(temp)}°C"

                    # end point of this ramp segment
                    x_end, y_end = x2, y2

                    # place label slightly to the right
                    x_text = x_end + self.text_offset
                    y_text = y_end

                    ax.text(
                        x_text, y_text,
                        label,
                        ha="left", va="center",
                        fontsize=fontsize,
                        transform=ax.transData,
                        family=self.font[0]
                    )
        # ----------------------------------------------------------------------
        # QUENCH BLOCK
        # ----------------------------------------------------------------------
        if getattr(self, "is_quenched", False):
            # first and last points
            y_first = points[0][1]
            x_last, y_last = points[-1]

            # Draw arrow from last → first
            ax.annotate(
                "",
                xy=(x_last, y_first),
                xytext=(x_last, y_last),
                arrowprops=dict(arrowstyle="->", color="red", linewidth=2)
            )

            # Label position with offset
            label_x = x_last + self.text_offset
            label_y = y_first

            ax.text(
                label_x, label_y,
                self.is_quenched,
                ha="left", va="center",
                fontsize=fontsize,
                family=self.font[0],
                transform=ax.transData,
                color="red"
            )
        
        old_xscale = ax.get_xlim()[1]-ax.get_xlim()[0]
        crop_axes_to_content(ax,self.l_marg,self.r_marg,self.t_marg,self.b_marg)

        new_xscale = ax.get_xlim()[1]-ax.get_xlim()[0]
        #print(f'old fontsize: {fontsize}')
        fontsize *= old_xscale/new_xscale
        #print(f'new fontsize: {fontsize}')
        for txt in ax.texts:
            txt.set_fontsize(fontsize)
        return fig
    '''

    def plot(self, show=False):
        import matplotlib.pyplot as plt

        # Create figure if missing OR closed
        if not hasattr(self, "fig") or self.fig is None or not plt.fignum_exists(self.fig.number):
            self.fig, self.ax = plt.subplots(figsize=(6, 4), dpi=100)
            self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        ax = self.ax

        # Set up coordinate system
        est_y = self.min_height * len(self.sections)
        ax.invert_yaxis()
        ax.set_xlim(0, est_y)
        ax.set_ylim(0, est_y)
        ax.autoscale(False)

        self.draw()
        if show:
            plt.show()
        return self.fig

    
    def draw(self):
        ax = self.ax
        fig = self.fig

        ax.clear()
        ax.axis("off")

        # Compute coordinates
        points = self.get_coords(ax)

        fontsize = self.font[1]

        for i, ((x1, y1), (x2, y2)) in enumerate(zip(points, points[1:])):
            # Draw the line segment
            ax.plot([x1, x2], [y1, y2], color="black", linewidth=self.line_width)

            if i < len(self.notes):
                top_text, bottom_text = self.notes[i]

                # midpoint
                xm = (x1 + x2) / 2
                ym = (y1 + y2) / 2

                # angle
                dx = x2 - x1
                dy = y2 - y1
                angle_deg = math.degrees(math.atan2(dy, dx))

                # --- Compute a small perpendicular offset in data units ---
                # Normal vector (unit)
                nx = -dy
                ny = dx
                L = math.hypot(nx, ny)
                nx /= L
                ny /= L

                # Apply your offset
                off = self.text_offset

                # Top label position
                top_x = xm + nx * off
                top_y = ym + ny * off

                # Bottom label position
                bottom_x = xm - nx * off
                bottom_y = ym - ny * off

                # --- TOP LABEL ---
                ax.text(
                    top_x, top_y,
                    top_text,
                    ha="center", va="bottom",
                    rotation=angle_deg,
                    rotation_mode="anchor",
                    transform_rotates_text=True,
                    transform=ax.transData,
                    fontsize=fontsize,
                    family=self.font[0]
                )

                # --- BOTTOM LABEL ---
                ax.text(
                    bottom_x, bottom_y,
                    bottom_text,
                    ha="center", va="top",
                    rotation=angle_deg,
                    rotation_mode="anchor",
                    transform_rotates_text=True,
                    transform=ax.transData,
                    fontsize=fontsize,
                    family=self.font[0]
                )
            # ------------------------------------------------------------------
            # RAMP-END TEMPERATURE LABEL (if next section is NOT a dwell)
            # ------------------------------------------------------------------

            if self.sections[i+1][0] == RAMP:
                is_last = (i == len(self.sections) - 2)
                if is_last:
                    next_is_dwell = False
                else:
                    next_is_dwell = (not is_last and self.sections[i+2][0] == DWELL)

                if is_last or not next_is_dwell:
                    # temperature at end of this ramp
                    temp = self.sections[i+1][1]
                    label = f"{int(temp)}°C"

                    # end point of this ramp segment
                    x_end, y_end = x2, y2

                    # place label slightly to the right
                    x_text = x_end + self.text_offset
                    y_text = y_end

                    ax.text(
                        x_text, y_text,
                        label,
                        ha="left", va="center",
                        fontsize=fontsize,
                        transform=ax.transData,
                        family=self.font[0]
                    )
        # ----------------------------------------------------------------------
        # QUENCH BLOCK
        # ----------------------------------------------------------------------
        if getattr(self, "is_quenched", False):
            # first and last points
            y_first = points[0][1]
            x_last, y_last = points[-1]

            # Draw arrow from last → first
            ax.annotate(
                "",
                xy=(x_last, y_first),
                xytext=(x_last, y_last),
                arrowprops=dict(arrowstyle="->", color="red", linewidth=2)
            )

            # Label position with offset
            label_x = x_last + self.text_offset
            label_y = y_first

            ax.text(
                label_x, label_y,
                self.is_quenched,
                ha="left", va="center",
                fontsize=fontsize,
                family=self.font[0],
                transform=ax.transData,
                color="red"
            )

        # --- cropping + font scaling ---
        old_xscale = ax.get_xlim()[1] - ax.get_xlim()[0]
        crop_axes_to_content(ax, self.l_marg, self.r_marg, self.t_marg, self.b_marg)
        new_xscale = ax.get_xlim()[1] - ax.get_xlim()[0]

        fontsize *= old_xscale / new_xscale
        for txt in ax.texts:
            txt.set_fontsize(fontsize)

        fig.canvas.draw_idle()

    def interactive(self):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Slider

        fig = self.plot()
        ax = self.ax

        # Compute needed height
        base_height = 6
        extra_height = len(sliders) * 0.2   # ~0.4 inches per slider
        fig.set_size_inches(8, base_height + extra_height)


        # --- Compute slider panel height ---
        slider_height = 0.03
        spacing = 0.04
        panel_height = len(sliders) * spacing + 0.05   # extra padding for labels

        # --- Shrink plot area to make room for sliders ---
        bbox = ax.get_position()

        ax.set_position([
            bbox.x0,
            bbox.y0 + panel_height,
            bbox.width,
            bbox.height - panel_height
        ])

        # --- Recompute bbox after moving plot ---
        bbox = ax.get_position()

        label_space = max([len(l) for l, s, e in sliders.values()])*.015

        left = bbox.x0 + label_space
        width = bbox.width - label_space - 0.06
        bottom_start = bbox.y0 - panel_height + 0.01   # ensure labels are visible

        # --- Create sliders ---
        self._sliders = {}

        for idx, (attr, (label, vmin, vmax)) in enumerate(sliders.items()):
            ax_slider = fig.add_axes([
                left,
                bottom_start + idx * spacing,
                width,
                slider_height
            ])

            slider = Slider(
                ax_slider,
                label,
                vmin,
                vmax,
                valinit=getattr(self, attr)
            )

            self._sliders[attr] = slider



        # --- Update function for ALL sliders ---
        def update(val):
            for attr, slider in self._sliders.items():
                setattr(self, attr, slider.val)

            # Rebuild font if needed
            self.font = [self.font_family, self.font_size]

            self.draw()

        # Connect all sliders to the same update function
        for slider in self._sliders.values():
            slider.on_changed(update)

        plt.show()


                