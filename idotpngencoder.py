#!/usr/bin/python

#lrdcq 2021/01/04

import sys,os
import struct
import binascii
import zlib
import getopt

##png filter function
##copy from https://github.com/drj11/pypng/blob/main/code/png.py

def undo_filter_sub(filter_unit, scanline, previous, result):
  ai = 0
  for i in range(filter_unit, len(result)):
    x = scanline[i]
    a = result[ai]
    result[i] = (x + a) & 0xff
    ai += 1


def undo_filter_up(filter_unit, scanline, previous, result):
  for i in range(len(result)):
    x = scanline[i]
    b = previous[i]
    result[i] = (x + b) & 0xff


def undo_filter_average(filter_unit, scanline, previous, result):
  ai = -filter_unit
  for i in range(len(result)):
    x = scanline[i]
    if ai < 0:
      a = 0
    else:
      a = result[ai]
    b = previous[i]
    result[i] = (x + ((a + b) >> 1)) & 0xff
    ai += 1


def undo_filter_paeth(filter_unit, scanline, previous, result):
  ai = -filter_unit
  for i in range(len(result)):
    x = scanline[i]
    if ai < 0:
      a = c = 0
    else:
      a = result[ai]
      c = previous[ai]
    b = previous[i]
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
      pr = a
    elif pb <= pc:
      pr = b
    else:
      pr = c
    result[i] = (x + pr) & 0xff
    ai += 1

def undo_filter(colorsize, filter_type, scanline, previous):
  result = scanline

  if filter_type == 0:
    return result

  if len(previous) < 1:
    previous = bytearray([0] * len(scanline))

  fn = (None,
        undo_filter_sub,
        undo_filter_up,
        undo_filter_average,
        undo_filter_paeth)[filter_type]
  fn(colorsize, scanline, previous, result)
  return result

##png filter function end

##png helper function

def read_block(rf):
  length = struct.unpack('>L', rf.read(4))[0]
  name = rf.read(4)
  data = rf.read(length)
  hash = rf.read(4)
  return name, data

def write_block(f, title, data):
  f.write(struct.pack('>L',len(data)))
  f.write(title)
  f.write(data)
  f.write(struct.pack('>l',binascii.crc32(title + data)))

##png helper function end

#main

def main(argv):

  #argv deal
  def printhelp():
    print('Usage: idotpngencoder.py -i <inputfile> -o <outputfile> -t <threadnumber>')
    print('- [threadnumber] determines the number of image section, minimum is 2')

  inputfile = ''
  outputfile = ''
  threadcount = 0
  try:
    opts, args = getopt.getopt(argv,"i:o:t:h",[])
  except getopt.GetoptError:
    printhelp()
    sys.exit(2)
  for opt, arg in opts:
    if opt == "-h":
      printhelp()
      sys.exit()
    elif opt == "-i":
      inputfile = arg
    elif opt == "-o":
      outputfile = arg
    elif opt == "-t":
      count = int(arg)
      if count > 1:
        threadcount = count
      else:
        print('Error: <threadcount> < 2')
  if not (inputfile and outputfile and threadcount):
    printhelp()
    sys.exit(2)

  #argv deal end

  #read input png

  rf = open(inputfile, "rb")
  rf.seek(2 * 4)
  
  #file chunk
  inputfile_chunks = []
  #file data
  idat_stream = ''
  #image info
  image_w = 0
  image_h = 0
  image_depth = 0
  image_color = 0

  while 1:
    name, data = read_block(rf)
    inputfile_chunks.append({'name': name, 'data': data})
    if name == 'IDAT':
      idat_stream += data
    elif name == 'IHDR':
      image_w = struct.unpack('>L', data[0:4])[0]
      image_h = struct.unpack('>L', data[4:8])[0]
      image_depth = struct.unpack('>B', data[8:9])[0]
      image_color = struct.unpack('>B', data[9:10])[0]
    elif name == 'IEND':
      break
    elif name == 'iDOT':
      print('Warn: <inputfile> just is a iDOT PNG file. Rebuild it.')

  colormap = bool(image_color & 1)
  greyscale = not(image_color & 2)
  alpha = bool(image_color & 4)
  color_planes = (3, 1)[greyscale or colormap]
  planes = color_planes + alpha
  psize = float(image_depth) / float(8) * planes
  if int(psize) == psize:
    psize = int(psize)

  linesize = image_w * psize + 1

  decoder = zlib.decompressobj()
  idat_decode = decoder.decompress(idat_stream)
  idat_decode += decoder.flush()

  idat_defilter = ''
  t_lastresult = bytearray()
  for x in range(0, image_h):
    linetype = idat_decode[(linesize * x)]
    linedata = bytearray(idat_decode[(linesize * x + 1):(linesize * (x + 1))])
    t_lastresult = undo_filter(4, struct.unpack('>B', linetype)[0], linedata, t_lastresult)
    idat_defilter += struct.pack('B',0x00)
    idat_defilter += bytes(t_lastresult)

  #read input png end

  #write png

  f = open(outputfile, "wb")

  f.write(struct.pack('>L',0x89504E47))
  f.write(struct.pack('>L',0x0D0A1A0A))

  #pop to IDAT
  while 1:
    chunk = inputfile_chunks.pop(0)
    name = chunk['name']
    data = chunk['data']
    if name == 'IDAT':
      break
    elif name == 'iDOT':
      continue
    write_block(f, name, data)
      

  #write iDOT after IHDR
  idot_pos = f.tell()
  section_h = int(image_h / threadcount)

  idot = ""
  idot += struct.pack('>L',threadcount)
  idot += struct.pack('>L',0x00000000)
  idot += struct.pack('>L',image_h - section_h * (threadcount - 1))
  idot += struct.pack('>L',0x00000028 + 12 * (threadcount - 2))
  for i in range(0, threadcount - 1):
    idot += struct.pack('>L',image_h - section_h * (threadcount - i - 1))
    idot += struct.pack('>L',section_h)
    idot += struct.pack('>L',0xFFFFFFFF) #

  write_block(f, "iDOT", idot)

  #wirte IDAT
  encoder = zlib.compressobj()

  #first section
  idat = encoder.compress(idat_decode[0:(linesize * (image_h - section_h * (threadcount - 1)))])
  idat += encoder.flush(zlib.Z_FULL_FLUSH)
  write_block(f, "IDAT", idat)

  for i in range(0, threadcount - 1):
    idat_pos = f.tell()
    start_h = image_h - section_h * (threadcount - i - 1)
    end_h = image_h - section_h * (threadcount - i - 2)
    idat = encoder.compress(idat_defilter[(linesize * start_h):(linesize * (start_h + 1))] + idat_decode[(linesize * (start_h + 1)):(linesize * end_h)])
    if i == threadcount - 2:
      idat += encoder.flush(zlib.Z_FINISH)
    else:
      idat += encoder.flush(zlib.Z_FULL_FLUSH)
    write_block(f, "IDAT", idat)

    #back to write idot offset
    now_pos = f.tell()
    f.seek(idot_pos + 32 + 12 * i)
    f.write(struct.pack('>L',idat_pos - idot_pos))
    f.seek(now_pos)

  #pop to IEND
  while 1:
    chunk = inputfile_chunks.pop(0)
    name = chunk['name']
    data = chunk['data']
    if name == 'IDAT':
      continue
    write_block(f, name, data)
    if name == 'IEND':
      break

  f.close()

  #write png end
  
  print('Finish!')

#boot
if __name__ == "__main__":
  main(sys.argv[1:])
