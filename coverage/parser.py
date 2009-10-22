"""Code parsing for Coverage."""

import glob, opcode, os, re, sys, token, tokenize

from coverage.backward import set, sorted, StringIO # pylint: disable-msg=W0622
from coverage.bytecode import ByteCodes, CodeObjects
from coverage.misc import nice_pair, CoverageException


class CodeParser:
    """Parse code to find executable lines, excluded lines, etc."""
    
    def __init__(self, text=None, filename=None, exclude=None):
        """
        Source can be provided as `text`, the text itself, or `filename`, from
        which text will be read.  Excluded lines are those that match `exclude`,
        a regex.
        
        """

        assert text or filename, "CodeParser needs either text or filename"
        self.filename = filename or "<code>"
        if not text:
            sourcef = open(self.filename, 'rU')
            self.text = sourcef.read()
            sourcef.close()
        self.text = self.text.replace('\r\n', '\n')

        self.exclude = exclude
        
        self.show_tokens = False

        # The text lines of the parsed code.
        self.lines = self.text.split('\n')

        # The line numbers of excluded lines of code.
        self.excluded = set()
        
        # The line numbers of docstring lines.
        self.docstrings = set()
        
        # A dict mapping line numbers to (lo,hi) for multi-line statements.
        self.multiline = {}
        
        # The line numbers that start statements.
        self.statement_starts = set()

        # Lazily-created ByteParser
        self._byte_parser = None
        
    def _get_byte_parser(self):
        """Create a ByteParser on demand."""
        if not self._byte_parser:
            self._byte_parser = ByteParser(text=self.text, filename=self.filename)
        return self._byte_parser
    byte_parser = property(_get_byte_parser)

    def _raw_parse(self):
        """Parse the source to find the interesting facts about its lines.
        
        A handful of member fields are updated.
        
        """
        # Find lines which match an exclusion pattern.
        if self.exclude:
            re_exclude = re.compile(self.exclude)
            for i, ltext in enumerate(self.lines):
                if re_exclude.search(ltext):
                    self.excluded.add(i+1)
    
        # Tokenize, to find excluded suites, to find docstrings, and to find
        # multi-line statements.
        indent = 0
        exclude_indent = 0
        excluding = False
        prev_toktype = token.INDENT
        first_line = None

        tokgen = tokenize.generate_tokens(StringIO(self.text).readline)
        for toktype, ttext, (slineno, _), (elineno, _), ltext in tokgen:
            if self.show_tokens:
                print("%10s %5s %-20r %r" % (
                    tokenize.tok_name.get(toktype, toktype),
                    nice_pair((slineno, elineno)), ttext, ltext
                    ))
            if toktype == token.INDENT:
                indent += 1
            elif toktype == token.DEDENT:
                indent -= 1
            elif toktype == token.OP and ttext == ':':
                if not excluding and elineno in self.excluded:
                    # Start excluding a suite.  We trigger off of the colon
                    # token so that the #pragma comment will be recognized on
                    # the same line as the colon.
                    exclude_indent = indent
                    excluding = True
            elif toktype == token.STRING and prev_toktype == token.INDENT:
                # Strings that are first on an indented line are docstrings.
                # (a trick from trace.py in the stdlib.)
                for i in range(slineno, elineno+1):
                    self.docstrings.add(i)
            elif toktype == token.NEWLINE:
                if first_line is not None and elineno != first_line:
                    # We're at the end of a line, and we've ended on a
                    # different line than the first line of the statement,
                    # so record a multi-line range.
                    rng = (first_line, elineno)
                    for l in range(first_line, elineno+1):
                        self.multiline[l] = rng
                first_line = None
                
            if ttext.strip() and toktype != tokenize.COMMENT:
                # A non-whitespace token.
                if first_line is None:
                    # The token is not whitespace, and is the first in a
                    # statement.
                    first_line = slineno
                    # Check whether to end an excluded suite.
                    if excluding and indent <= exclude_indent:
                        excluding = False
                    if excluding:
                        self.excluded.add(elineno)
                        
            prev_toktype = toktype

        # Find the starts of the executable statements.
        self.statement_starts.update(self.byte_parser._find_statements())

    def _map_to_first_line(self, lines, ignore=None):
        """Map the line numbers in `lines` to the correct first line of the
        statement.
        
        Skip any line mentioned in `ignore`.
        
        Returns a sorted list of the first lines.
        
        """
        ignore = ignore or []
        lset = set()
        for l in lines:
            if l in ignore:
                continue
            rng = self.multiline.get(l)
            if rng:
                new_l = rng[0]
            else:
                new_l = l
            if new_l not in ignore:
                lset.add(new_l)
        lines = list(lset)
        return sorted(lines)
    
    def parse_source(self):
        """Parse source text to find executable lines, excluded lines, etc.

        Return values are 1) a sorted list of executable line numbers,
        2) a sorted list of excluded line numbers, and 3) a dict mapping line
        numbers to pairs (lo,hi) for multi-line statements.
        
        """
        self._raw_parse()
        
        excluded_lines = self._map_to_first_line(self.excluded)
        ignore = excluded_lines + list(self.docstrings)
        lines = self._map_to_first_line(self.statement_starts, ignore)
    
        return lines, excluded_lines, self.multiline

    def arc_info(self):
        """Get information about the arcs available in the code."""
        arcs = self.byte_parser._all_arcs()
        return sorted(arcs)

## Opcodes that guide the ByteParser.

def _opcode(name):
    """Return the opcode by name from the opcode module."""
    return opcode.opmap[name]

def _opcode_set(*names):
    """Return a set of opcodes by the names in `names`."""
    return set([_opcode(name) for name in names])

# Opcodes that leave the code object.
OPS_CODE_END = _opcode_set('RETURN_VALUE')

# Opcodes that unconditionally end the code chunk.
OPS_CHUNK_END = _opcode_set(
    'JUMP_ABSOLUTE', 'JUMP_FORWARD', 'RETURN_VALUE', 'RAISE_VARARGS',
    'BREAK_LOOP', 'CONTINUE_LOOP',
    )

# Opcodes that push a block on the block stack.
OPS_PUSH_BLOCK = _opcode_set('SETUP_LOOP', 'SETUP_EXCEPT', 'SETUP_FINALLY')

# Block types for exception handling.
OPS_EXCEPT_BLOCKS = _opcode_set('SETUP_EXCEPT', 'SETUP_FINALLY')

# Opcodes that pop a block from the block stack.
OPS_POP_BLOCK = _opcode_set('POP_BLOCK')

# Opcodes that have a jump destination, but aren't really a jump.
OPS_NO_JUMP = _opcode_set('SETUP_EXCEPT', 'SETUP_FINALLY')

# Individual opcodes we need below.
OP_BREAK_LOOP = _opcode('BREAK_LOOP')
OP_END_FINALLY = _opcode('END_FINALLY')


class ByteParser:
    """Parse byte codes to understand the structure of code."""

    def __init__(self, code=None, text=None, filename=None):

        if code:
            self.code = code
        else:
            if not text:
                assert filename, "If no code or text, need a filename"
                sourcef = open(filename, 'rU')
                text = sourcef.read()
                sourcef.close()

            try:
                # Python 2.3 and 2.4 don't like partial last lines, so be sure
                # the text ends nicely for them.
                self.code = compile(text + '\n', filename, "exec")
            except SyntaxError:
                _, synerr, _ = sys.exc_info()
                raise CoverageException(
                    "Couldn't parse '%s' as Python source: '%s' at line %d" %
                        (filename, synerr.msg, synerr.lineno)
                    )

    def child_parsers(self):
        """Iterate over all the code objects nested within this one, starting with self."""
        return map(lambda c: ByteParser(code=c), CodeObjects(self.code))

    # Getting numbers from the lnotab value changed in Py3.0.    
    if sys.hexversion >= 0x03000000:
        def _lnotab_increments(self, lnotab):
            """Return a list of ints from the lnotab bytes in 3.x"""
            return list(lnotab)
    else:
        def _lnotab_increments(self, lnotab):
            """Return a list of ints from the lnotab string in 2.x"""
            return [ord(c) for c in lnotab]

    def _bytes_lines(self):
        """Map byte offsets to line numbers in `code`.
    
        Uses co_lnotab described in Python/compile.c to map byte offsets to
        line numbers.  Returns a list: [(b0, l0), (b1, l1), ...]
    
        """
        # Adapted from dis.py in the standard library.
        byte_increments = self._lnotab_increments(self.code.co_lnotab[0::2])
        line_increments = self._lnotab_increments(self.code.co_lnotab[1::2])
    
        bytes_lines = []
        last_line_num = None
        line_num = self.code.co_firstlineno
        byte_num = 0
        for byte_incr, line_incr in zip(byte_increments, line_increments):
            if byte_incr:
                if line_num != last_line_num:
                    bytes_lines.append((byte_num, line_num))
                    last_line_num = line_num
                byte_num += byte_incr
            line_num += line_incr
        if line_num != last_line_num:
            bytes_lines.append((byte_num, line_num))
        return bytes_lines
    
    def _find_statements(self):
        """Find the statements in `self.code`.
        
        Return a set of line numbers that start statements.  Recurses into all
        code objects reachable from `self.code`.
        
        """
        stmts = set()
        for bp in self.child_parsers():
            # Get all of the lineno information from this code.
            for _, l in bp._bytes_lines():
                stmts.add(l)
        return stmts
    
    def _disassemble(self):
        """Disassemble code, for ad-hoc experimenting."""
        
        import dis
        
        for bp in self.child_parsers():
            print("\n%s: " % bp.code)
            dis.dis(bp.code)
            print("Bytes lines: %r" % bp._bytes_lines())

        print("")

    def _line_for_byte(self, bytes_lines, byte):
        last_line = 0
        for b, l in bytes_lines:
            if b == byte:
                return l
            elif b > byte:
                return last_line
            else:
                last_line = l
        return last_line

    def _split_into_chunks(self):
        class Chunk(object):
            """A sequence of bytecodes with exits to other bytecodes.
            
            An exit of -1 means the chunk can leave the code (return).
            
            """
            def __init__(self, byte, line=0):
                self.byte = byte
                self.line = line
                self.length = 0
                self.exits = set()
                
            def __repr__(self):
                return "<%d:%d(%d) %r>" % (self.byte, self.line, self.length, list(self.exits))

        # The list of chunks so far, and the one we're working on.
        chunks = []
        chunk = None
        bytes_lines_map = dict(self._bytes_lines())
        
        # The block stack: loops and try blocks get pushed here for the
        # implicit jumps that can occur.
        # Each entry is a tuple: (block type, destination)
        block_stack = []
        
        for bc in ByteCodes(self.code.co_code):
            # Maybe have to start a new block
            if bc.offset in bytes_lines_map:
                if chunk:
                    chunk.exits.add(bc.offset)
                chunk = Chunk(bc.offset, bytes_lines_map[bc.offset])
                chunks.append(chunk)
                
            if not chunk:
                chunk = Chunk(bc.offset)
                chunks.append(chunk)

            # Look at the opcode                
            if bc.jump_to >= 0 and bc.op not in OPS_NO_JUMP:
                # The opcode has a jump, it's an exit for this chunk.
                chunk.exits.add(bc.jump_to)
            
            if bc.op in OPS_CODE_END:
                # The opcode can exit the code object.
                chunk.exits.add(-1)
            elif bc.op in OPS_PUSH_BLOCK:
                # The opcode adds a block to the block_stack.
                block_stack.append((bc.op, bc.jump_to))
            elif bc.op in OPS_POP_BLOCK:
                # The opcode pops a block from the block stack.
                block_stack.pop()
            elif bc.op in OPS_CHUNK_END:
                # This opcode forces the end of the chunk.
                if bc.op == OP_BREAK_LOOP:
                    # A break is implicit: jump where the top of the
                    # block_stack points.
                    chunk.exits.add(block_stack[-1][1])
                chunk = None
            elif bc.op == OP_END_FINALLY:
                if block_stack:
                    # A break that goes through a finally will jump to whatever
                    # block is on top of the stack.
                    chunk.exits.add(block_stack[-1][1])
                # For the finally clause we need to find the closest exception
                # block, and use its jump target as an exit.
                for iblock in range(len(block_stack)-1, -1, -1):
                    if block_stack[iblock][0] in OPS_EXCEPT_BLOCKS:
                        chunk.exits.add(block_stack[iblock][1])
                        break

        if chunks:
            chunks[-1].length = bc.next_offset - chunks[-1].byte
            for i in range(len(chunks)-1):
                chunks[i].length = chunks[i+1].byte - chunks[i].byte

        return chunks

    def _arcs(self):
        chunks = self._split_into_chunks()
        
        # A map from byte offsets to chunks jumped into.
        byte_chunks = dict([(c.byte, c) for c in chunks])

        # Build a map from byte offsets to actual lines reached.
        byte_lines = {-1:[-1]}
        bytes_to_add = set([c.byte for c in chunks])
        
        while bytes_to_add:
            byte_to_add = bytes_to_add.pop()
            if byte_to_add in byte_lines or byte_to_add == -1:
                continue
            
            # Which lines does this chunk lead to?
            bytes_considered = set()
            bytes_to_consider = [byte_to_add]
            lines = set()
            
            while bytes_to_consider:
                byte = bytes_to_consider.pop()
                bytes_considered.add(byte)
                
                # Find chunk for byte
                try:
                    ch = byte_chunks[byte]
                except KeyError:
                    for ch in chunks:
                        if ch.byte <= byte < ch.byte+ch.length:
                            break
                    else:
                        # No chunk for this byte!
                        raise Exception("Couldn't find a chunk for byte %d" % byte)
                    byte_chunks[byte] = ch
                    
                if ch.line:
                    lines.add(ch.line)
                else:
                    for ex in ch.exits:
                        if ex == -1:
                            lines.add(-1)
                        elif ex not in bytes_considered:
                            bytes_to_consider.append(ex)

                bytes_to_add.update(ch.exits)

            byte_lines[byte_to_add] = lines
        
        # Figure out for each chunk where the exits go.
        arcs = set()
        for chunk in chunks:
            if chunk.line:
                for ex in chunk.exits:
                    for exit_line in byte_lines[ex]:
                        if chunk.line != exit_line:
                            arcs.add((chunk.line, exit_line))
        for line in byte_lines[0]:
            arcs.add((-1, line))
        
        return arcs
        
    def _all_chunks(self):
        chunks = []
        for bp in self.child_parsers():
            chunks.extend(bp._split_into_chunks())
        
        return chunks

    def _all_arcs(self):
        arcs = []
        for bp in self.child_parsers():
            arcs.extend(bp._arcs())
        
        return arcs


class AdHocMain(object):
    """An ad-hoc main for code parsing experiments."""
    
    def main(self, args):
        """A main function for trying the code from the command line."""

        from optparse import OptionParser

        parser = OptionParser()
        parser.add_option(
            "-c", action="store_true", dest="chunks", help="Check byte chunks"
            )
        parser.add_option(
            "-d", action="store_true", dest="dis", help="Disassemble"
            )
        parser.add_option(
            "-R", action="store_true", dest="recursive", help="Recurse to find source files"
            )
        parser.add_option(
            "-s", action="store_true", dest="source", help="Show analyzed source"
            )
        parser.add_option(
            "-t", action="store_true", dest="tokens", help="Show tokens"
            )
        
        options, args = parser.parse_args()
        if options.recursive:
            if args:
                root = args[0]
            else:
                root = "."
            for root, _, _ in os.walk(root):
                for f in glob.glob(root + "/*.py"):
                    self.adhoc_one_file(options, f)
        else:
            self.adhoc_one_file(options, args[0])

    def adhoc_one_file(self, options, filename):
        if options.dis or options.chunks:
            try:
                bp = ByteParser(filename=filename)
            except CoverageException:
                _, err, _ = sys.exc_info()                
                print("%s" % (err,))
                return

        if options.dis:
            print("Main code:")
            bp._disassemble()

        if options.chunks:
            chunks = bp._all_chunks()
            if options.recursive:
                print("%6d: %s" % (len(chunks), filename))
            else:
                print("Chunks: %r" % chunks)
                arcs = bp._all_arcs()
                print("Arcs: %r" % arcs)

        if options.source or options.tokens:
            cp = CodeParser(filename=filename, exclude=r"no\s*cover")
            cp.show_tokens = options.tokens
            cp._raw_parse()

            if options.source:
                arc_chars = {}
                if options.chunks:
                    for lfrom, lto in sorted(arcs):
                        if lfrom == -1:
                            arc_chars[lto] = arc_chars.get(lto, '') + 'v'
                        elif lto == -1:
                            arc_chars[lfrom] = arc_chars.get(lfrom, '') + '^'
                        else:
                            if lfrom == lto-1:
                                # Don't show obvious arcs.
                                continue
                            if lfrom < lto:
                                l1, l2 = lfrom, lto
                            else:
                                l1, l2 = lto, lfrom
                            w = max([len(arc_chars.get(l, '')) for l in range(l1, l2+1)])
                            for l in range(l1, l2+1):
                                if l == lfrom:
                                    ch = '<'
                                elif l == lto:
                                    ch = '>'
                                else:
                                    ch = '|'
                                arc_chars[l] = arc_chars.get(l, '').ljust(w) + ch

                arc_width = 0
                if arc_chars:
                    arc_width = max([len(a) for a in arc_chars.values()])
                    
                for i, ltext in enumerate(cp.lines):
                    lineno = i+1
                    m0 = m1 = m2 = a = ' '
                    if lineno in cp.statement_starts:
                        m0 = '-'
                    if lineno in cp.docstrings:
                        m1 = '"'
                    if lineno in cp.excluded:
                        m2 = 'x'
                    a = arc_chars.get(lineno, '').ljust(arc_width)
                    print("%4d %s%s%s%s %s" % (lineno, m0, m1, m2, a, ltext))


if __name__ == '__main__':
    AdHocMain().main(sys.argv[1:])
