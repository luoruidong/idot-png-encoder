# idot-png-encoder
A Python Script to convert Normal PNG Image to Apple iDOT PNG Image (Multi-threaded Decoding PNG).

## Usage
```
idotpngencoder.py -i <inputfile> -o <outputfile> -t <threadnumber>
```
Input Params:
- inputfile & outputfile: That's it. Of course input file must be a PNG file.
- threadnumber:  Determines the number of image section, minimum is 2

## Discussion
1. The precise format of iDOT chunk now we known is here [http://lrd.tw/LX9E](http://lrd.tw/LX9E). Just go further than before.
2. The speed of this task with Python is too slow and dangerous. Do not use this script in Production Environment.

Contact: [https://lrdcq.com](https://lrdcq.com)