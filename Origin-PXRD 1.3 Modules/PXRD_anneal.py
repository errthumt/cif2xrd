import warnings

# Axes3D is not included with Origin's native matplotlib, but it is not necessary for this package
warnings.filterwarnings(
    "ignore",
    message="Unable to import Axes3D",
    category=UserWarning,
    module="matplotlib.projections"
)

import tkinter as tk
import tkinter.font as tkfont
import math
import matplotlib.pyplot as plt
import originpro as op #type: ignore
from itertools import zip_longest
import sys
import os
from matplotlib.transforms import ScaledTranslation
from pathlib import Path

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


class InvertedCanvas(tk.Canvas):
    def __init__(self, master, width, height, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self._h = height

    def line(self, x1, y1, x2, y2, **kwargs):
        # Flip Y before drawing
        y1 = self._h - y1
        y2 = self._h - y2
        return self.create_line(x1, y1, x2, y2, **kwargs)

    def point(self, x, y, r=3, **kwargs):
        y = self._h - y
        return self.create_oval(x-r, y-r, x+r, y+r, **kwargs)
    
    def text(self, x, y, text, **kwargs):
        y = self._h - y
        return self.create_text(x, y, text=text, **kwargs)


class profile:
    def __init__(self,start_temp=25, min_height=6, add_temps="", ramp_width=4, dwell_width=6, font_size=16, font_family="Arial", text_offset=0.6, line_width=2, l_marg=10,r_marg=10,t_marg=10,b_marg=10):
        self.start_temp = start_temp
        self.min_height=min_height
        self.add_temps=add_temps
        self.ramp_width=ramp_width
        self.dwell_width=dwell_width
        self.font=[font_family, font_size]
        self.text_offset=text_offset
        self.line_width=line_width
        self.l_marg=l_marg
        self.r_marg=r_marg
        self.t_marg=t_marg
        self.b_marg=b_marg
        self.sections = [[START,start_temp]]
        self.notes = []
        self.is_quenched = False

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
        try:
            unique_temps = [int(float(x)) for x in str(self.add_temps).split(";") if str(self.add_temps).strip() != ""]
        except Exception as e:
            op.lt_exec('type -b "Your \"Add Temps\" values could not be read correctly.')
            print(e)
            unique_temps = []
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
       
    def copy_to_clipboard(self):
        return


    def save_canvas_png(self):
        return

    def plot(self):
        # --- Create figure and axis ---
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

        self.text_trans = ax.transData + ScaledTranslation(0, 0, ax.figure.dpi_scale_trans)

        fig.subplots_adjust(left=0,right=1,top=1,bottom=0)
        # Invert Y to match your InvertedCanvas behavior
        est_y = self.min_height*len(self.sections)
        ax.invert_yaxis()
        ax.set_xlim(0, est_y)
        ax.set_ylim(0, est_y)
        ax.autoscale(False)

        points = self.get_coords(ax)
        
        '''
        ax.set_xlim(min(x for x, y in points)-self.l_marg,
                            max(x for x, y in points)+self.r_marg)
        ax.set_ylim(min(y for x, y in points)-self.b_marg,
                max(y for x, y in points)+self.t_marg)
        '''

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
        save_file = op.get_lt_str('fname$')

        save_path = Path(save_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(save_file, bbox_inches='tight', pad_inches=0)

        plt.close(fig)

def make_anneal_template():
    wbook = op.load_book('PXRD_anneal_template.ogwu')
    wks = wbook[0]
    op.lt_exec("wks.labels(-O)")

default_params["anneal"] = {
    "start_temp":      25,   # int
    "min_height":      6.0,   # float
    "add_temps":       "",   # comma‑separated string of numbers, e.g. "500,600,700"
    "ramp_width":      4.0,   # float
    "dwell_width":     6.0,   # float
    "font_size":       30.0,   # float
    "font_family":     "Arial",   # int (0=Arial, 1=Times New Roman, etc.)
    "text_offset":     0.6,   # float
    "line_width":      3.0,   # float
    "l_marg":          1.0,   # float
    "r_marg":          1.0,   # float
    "t_marg":          1.0,   # float
    "b_marg":          1.0    # float
}


def make_anneal_plot(cleaned_params=default_params["anneal"]):
    wb = op.find_book()
    wks = wb[0]

    try:
        types = wks.to_list('Type')
        temps = wks.to_list('Temperature')
        notes = wks.to_list('Time/Comment')

        #keys = wks.to_list('Variable')
        #values = wks.to_list('Value')
    except:
        op.lt_exec('type -b "At least one required column not found. It is recommended to use the provided template worksheet.')
        return



    commands = list(zip_longest(types,temps,notes))
    myProf = profile(**cleaned_params)
    for type, temp, note in commands:
        method = getattr(myProf,type,None)
        if method is not None:
            if type.lower() == RAMP:
                method(temp,note)
            else:
                method(note)
    
    myProf.plot()
    wks = wb[1]
    wks.activate()
    comment = f'Image Saved to:\n{op.get_lt_str("fname$")}'
    lt_cmd = f'''
        insertimg resize:=1 orng:=col(1)[1];
        col(1)[C]$ = "{comment}";
    '''
    op.lt_exec(lt_cmd)

if __name__ == "__main__":
    # sys.argv[0] = script name
    # sys.argv[1] = first argument from LabTalk
    template_mode = sys.argv[1]=="template" if len(sys.argv)>1 else False

    if template_mode:
        make_anneal_template()
    else:
        param_string = sys.argv[2] if len(sys.argv)>2 else ""
        params = parse_params(param_string)
        cleaned_params = clean_parameters(params, defaults=default_params["anneal"])
        make_anneal_plot(cleaned_params)
