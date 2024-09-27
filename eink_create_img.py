#!/usr/bin/python3

import sys
import argparse, requests, json
from PIL import Image, ImageDraw, ImageFont


class Logger:
  def __init__(self, verbosity: int):
    self.verbosity = verbosity

  def _log(self, v, f, *m):
    if self.verbosity >= v:
      print(file=f, *m)

  def info(self, *m):
    self._log(1, sys.stdout, *m)

  def debug(self, *m):
    self._log(2, sys.stdout, *m)

  def log(self, *m):
    self._log(0, sys.stdout, *m)

  def error(self, *m):
    self._log(0, sys.stderr, *m)


class Payload(object):
  def __init__(self, j):
    self.__dict__ = json.loads(j)


sizes = {
  '152x152': [152, 152],
  '1.54':    [152, 152],
  '296x128': [296, 128],
  '2.9w':    [296, 128],
  '128x296': [128, 296],
  '2.9t':    [128, 296],
  '400x300': [400, 300],
  '4.2w':    [400, 300],
  '300x400': [300, 400],
  '4.2t':    [300, 400],
}
palette = [
  255, 255, 255,  # white
  0, 0, 0,        # black
  255, 0, 0       # red

]

# writes text in different fonts, sizes, colors, positions and aligns
# lines: line[]
# line: object
# - t str   text
# - f str   font (path, .ttf)
# - s uint  font size
# - c [0~2] text color
# - x uint  x pos of upper left corner
# - y uint  y pos of upper left corner
# - a uint  angle (degrees, 0=normal/ horizontal ltr)
def gen_text(draw: ImageDraw, image: Image, lines):
  for line in lines:
    font = ImageFont.truetype(font=line['f'], size=line['s'])
    # bbox := [left, top, right, bottom]
    bbox = draw.textbbox(xy=(0, 0), text=line['t'], font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pos_x = line['x']
    if pos_x == 'c':
      pos_x = (image.width - text_w) // 2
    elif pos_x == 'r':
      pos_x = image.width - text_w
    elif pos_x == 'l':
      pos_x = 0
    pos_y = line['y']
    if pos_y == 'm':
      pos_y = (image.width - text_h) // 2
    elif pos_y == 'b':
      pos_y = image.height - text_h
    elif pos_y == 't':
      pos_y = 0
    draw.text((pos_x, pos_y), line['t'], fill=line['c'], font=font)

def main(l: Logger, target, size, dither, rotation, gen_f, gen_a):
  l.info(f'generating image with\n\
  \tverbosity={l.verbosity}\n\
  \ttarget={target}\n\
  \tsize={size} ({sizes[size][0]}x{sizes[size][1]} px)\n\
  \tdither={dither}\n\
  \trotation={rotation}°\n\
  \tgen_a={gen_a}')

  l.debug('Create a new paletted image with indexed colors')
  image = Image.new('P', (sizes[size][0], sizes[size][1]))
  image.putpalette(palette)

  l.debug('Initialize the drawing context')
  draw = ImageDraw.Draw(image)

  l.debug('Write the text on the image')
  gen_f(draw, image, gen_a)

  l.debug('OpenEPaperLink expects wide/ horizontal images')
  if image.height > image.width:
    rotation += 90
  l.debug('only flipping is possible. rotation is achieved by using inverted image size')
  if rotation != 0:
    image = image.rotate(rotation, expand=True, fillcolor="white")

  l.debug('Convert the image to 24-bit RGB')
  rgb_image = image.convert('RGB')

  l.debug('Save the image as JPEG with maximum quality')
  rgb_image.save(target['file'], 'JPEG', quality="maximum")

  if not ('ap' in target or 'tag' in target):
    l.log('Image created successfully')
    return 0

  l.debug('Prepare the HTTP POST request')
  url = target['ap'] + "/imgupload"
  payload = {"dither": dither, "mac": target['tag']}  # Additional POST parameter
  files = {"file": open(target['file'], "rb")}  # File to be uploaded
  l.debug(f'HTTP POST request:\n\
    \turl={url}\n\
    \tpayload={payload}\n\
    \tfiles={files}\n')
  l.debug('Send the HTTP POST request')
  try:
    response = requests.post(url, data=payload, files=files, timeout=5)

    l.debug('Check the response status')
    if response.status_code == 200:
      l.log("Image uploaded successfully!")
      return 0
    else:
      l.error("Failed to upload the image.")
      return 1
  except requests.exceptions.ReadTimeout as e:
    l.error('Connection Error: Request timed out')
  except requests.exceptions.ConnectionError as e:
    l.error(f'Connection error: {e.args[0]}')
  except Exception as e:
    l.error(f'unexpected exception (type={type(e)}')
    l.error(e)
  return 1

# i'll fix it later (tm)
if __name__ == '__main__':
  parser = argparse.ArgumentParser(prog='eink_create_img',
                                  description='Creates a new image for eink displays.',
                                  epilog='Repo: https://github.com/Luka5w/eink.git (will change some day…)') #TODO 2023-12-03
  parser.add_argument('-d', '--dither', dest='dither',
                      required=False, action='store_const', const=1, default=0,
                      help='sets dither to 1 if set (default: 0); use when you\'re sending photos etc')
  parser.add_argument('-i', '--input', dest='input',
                      required=False, nargs='+',
                      help='json input to interprete')
  parser.add_argument('-o', '--output', dest='output',
                      required=True,
                      help='the path to the file to generate')
  parser.add_argument('-r', '--rotate', dest='rotation',
                      required=False, choices=['0', '180'], default=0,
                      help='the rotation of the whole image')
  parser.add_argument('-s', '--size', dest='size',
                      required=True,  choices=sizes.keys(),
                      help='the Tag eink screen size')
  parser.add_argument('-u', '--upload', dest='target',
                      required=False, nargs=2, metavar=('AP', 'TAG'),
                      help='upload image to the OpenEPaperLink AP (AP = protocol + FQDN + PORT, TAG = MAC address')
  parser.add_argument('-v', '--verbose', dest='verbosity',
                      required=False, action='count', default=0,
                      help='verbose logging')
  parser.add_argument('--version', action='version', version='1.0.1')
  args = parser.parse_args()
  l = Logger(args.verbosity)
  l.debug('Handling args')
  target = {
    'file': args.output
  }
  if hasattr(args, 'target') and type(args.target) == list:
    l.debug('Target found → upload image')
    target['ap'] = args.target[0]
    target['tag'] = args.target[1]
  lines = []
  for line in args.input:
    l.debug(f'Line found:\t{line}')
    lines.append(Payload(line).__dict__)
  exit(main(l, target, args.size, args.dither, int(args.rotation), gen_text, lines))

# vim: set ff=unix ts=2 sw=2 expandtab:
