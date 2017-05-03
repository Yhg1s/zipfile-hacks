# -*- python -*-

from __future__ import print_function

import argparse
import os
import zipfile

def force_zip64_zipfiles():
    # Trick the zipfile module into always producing ZIP files using ZIP64
    # by lowering the limits and by making allowZip64 default to True.
    assert zipfile.ZIP64_LIMIT != 0
    zipfile.ZIP64_LIMIT = 0
    zipfile.ZIP_FILECOUNT_LIMIT = 0

    orig_init = zipfile.ZipFile.__init__
    def new_init(*args, **kwargs):
        if 'allowZip64' not in kwargs:
            kwargs['allowZip64'] = True
        return orig_init(*args, **kwargs)
    zipfile.ZipFile.__init__ = new_init

    orig_close = zipfile.ZipFile.close
    def new_close(self):
        if self.fp is None:
            orig_filename = self.filename
        else:
            orig_filename = self.fp.name
        orig_close(self)
        # zipfile.ZipFile's close() correctly writes a zip64 central
        # directory records when we set ZIP64_LIMIT low enough, but doesn't
        # set the values in the regular end-of-central-directory record to
        # the magic values that mean "use zip64". This is all in the
        # monolithic close method, and we can't easily fix that -- so fix
        # the zipfile after the fact. This is not pretty :S

        # The original file may not have been closed yet, but it will have
        # been flushed, so re-opening the file should be safe everywhere but
        # Windows.
        with open(orig_filename, 'r+b') as f:
            # Don't want to bother with dealing with comments, so assume that
            # there isn't one.
            f.seek(-2, os.SEEK_END)
            assert f.read() == b'\x00\x00'
            # Overwrite the "number of central directory entries on this
            # disk", "total number of entries in the central directory",
            # "size of the central directory" and "offset of the central
            # directory" records (12 bytes, 14 bytes before the end of the
            # file).
            f.seek(-14, os.SEEK_END)
            f.write(b'\xff' * 12)
            f.flush()
    zipfile.ZipFile.close = new_close

    # Python 3.6 added an _open_to_write method that writestr uses, which
    # also has to be convinced to write ZIP64 headers.
    if hasattr(zipfile.ZipFile, '_open_to_write'):
        orig_open_to_write = zipfile.ZipFile._open_to_write
        def new_open_to_write(self, *args, **kwargs):
            kwargs['force_zip64'] = self._allowZip64
            return orig_open_to_write(self, *args, **kwargs)
        zipfile.ZipFile._open_to_write = new_open_to_write

def traverse(files):
    files = list(files)
    for name in files:
        if os.path.isfile(name):
            yield name
        elif os.path.isdir(name):
            files.extend(os.path.join(name, f) for f in os.listdir(name))
        else:
            warnings.warn(UserWarning,
                          'ignoring {!r}: unknown file type)'.format(name))

def create_zip(args):
    with open(args.zipfile, 'wb') as f:
        if args.preamble:
            f.write(args.preamble.encode('ascii'))
        zf = zipfile.ZipFile(f, args.mode)
        for name in traverse(args.files):
            if args.verbose:
                print('Adding {!r}'.format(name))
            zf.write(name, compress_type=zipfile.ZIP_DEFLATED)
        zf.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='print files being added')
    parser.add_argument('--mode', choices=('w', 'a'), default='w')
    parser.add_argument('--preamble', default='')
    parser.add_argument('--force-zip64', action='store_true',
                        help='force generated ZIP file to use ZIP64')
    parser.add_argument('zipfile', help='zipfile to create')
    parser.add_argument('files', help='files to zip up', nargs='+')
    args = parser.parse_args()

    if args.force_zip64:
        force_zip64_zipfiles()

    create_zip(args)

if __name__ == '__main__':
    main()
