from cif2xrd.pattern import simPattern


single_cif = r'C:\Users\travi\cif2xrd\tests\CIF\BaSb2.cif'

def print_single_cif():
    save_path = r'C:\Users\travi\cif2xrd\tests\patterns\BaSb2_pattern.txt'
    pattern = simPattern(single_cif)
    pattern.save_pattern(save_path)
    print(pattern.params)

if __name__ == "__main__":
    print_single_cif()