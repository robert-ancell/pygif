This repository contains a Python encoder and decoder for the [GIF file format](https://www.w3.org/Graphics/GIF/spec-gif89a.txt).

The easiest way to get PyGIF is to install using pip:
```
pip install pygif
```

The following will generate an 8x8 checkerboard image:
```python
import gif

writer = gif.Writer (open ('checkerboard.gif', 'wb'))
writer.write_header ()
writer.write_screen_descriptor (8, 8, has_color_table = True, depth = 1)
writer.write_color_table ([(0, 0, 0), (255, 255, 255)], 1)
writer.write_image (8, 8, 1, [ 1, 0, 1, 0, 1, 0, 1, 0,
                               0, 1, 0, 1, 0, 1, 0, 1,
                               1, 0, 1, 0, 1, 0, 1, 0,
                               0, 1, 0, 1, 0, 1, 0, 1,
                               1, 0, 1, 0, 1, 0, 1, 0,
                               0, 1, 0, 1, 0, 1, 0, 1,
                               1, 0, 1, 0, 1, 0, 1, 0,
                               0, 1, 0, 1, 0, 1, 0, 1 ])
writer.write_trailer ()
```

The following will decode that image:
```python
import gif

file = open ('checkerboard.gif', 'rb')
reader = gif.Reader ()
reader.feed (file.read ())
if reader.has_screen_descriptor ():
    print ('Size: %dx%d' % (reader.width, reader.height))
    print ('Colors: %s' % repr (reader.color_table))
    for block in reader.blocks:
        if isinstance (block, gif.Image):
            print ('Pixels: %s' % repr (block.get_pixels ()))
    if reader.has_unknown_block ():
        print ('Encountered unknown block')
    elif not reader.is_complete ():
        print ('Missing trailer')
else:
    print ('Not a valid GIF file')
```

Giving the following output:
```
Size: 8x8
Colors: [(0, 0, 0), (255, 255, 255)]
Pixels: [1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1]
```
