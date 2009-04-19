"""Source file annotation for coverage.py"""

import os, re

from coverage.report import Reporter

class AnnotateReporter(Reporter):
    def __init__(self, coverage, ignore_errors=False):
        super(AnnotateReporter, self).__init__(coverage, ignore_errors)
        self.directory = None
        
    blank_re = re.compile(r"\s*(#|$)")
    else_re = re.compile(r"\s*else\s*:\s*(#|$)")

    def report(self, morfs, directory=None, omit_prefixes=None):
        self.find_code_units(morfs, omit_prefixes)

        self.directory = directory
        if self.directory and not os.path.exists(self.directory):
            os.makedirs(self.directory)

        for cu in self.code_units:
            try:
                if not cu.relative:
                    continue
                statements, excluded, missing, _ = self.coverage.analyze(cu)
                self.annotate_file(cu, statements, excluded, missing)
            except KeyboardInterrupt:
                raise
            except:
                if not self.ignore_errors:
                    raise
                
    def annotate_file(self, cu, statements, excluded, missing):
        """Annotate a single file.
        
        `cu` is the CodeUnit for the file to annotate.
        
        """
        filename = cu.filename
        source = open(filename, 'r')
        if self.directory:
            dest_file = os.path.join(self.directory, cu.flat_rootname()) + ".py"
        else:
            dest_file = filename
        dest_file += ",cover"
        dest = open(dest_file, 'w')

        lineno = 0
        i = 0
        j = 0
        covered = True
        while True:
            line = source.readline()
            if line == '':
                break
            lineno += 1
            while i < len(statements) and statements[i] < lineno:
                i += 1
            while j < len(missing) and missing[j] < lineno:
                j += 1
            if i < len(statements) and statements[i] == lineno:
                covered = j >= len(missing) or missing[j] > lineno
            if self.blank_re.match(line):
                dest.write('  ')
            elif self.else_re.match(line):
                # Special logic for lines containing only 'else:'.  
                if i >= len(statements) and j >= len(missing):
                    dest.write('! ')
                elif i >= len(statements) or j >= len(missing):
                    dest.write('> ')
                elif statements[i] == missing[j]:
                    dest.write('! ')
                else:
                    dest.write('> ')
            elif lineno in excluded:
                dest.write('- ')
            elif covered:
                dest.write('> ')
            else:
                dest.write('! ')
            dest.write(line)
        source.close()
        dest.close()
