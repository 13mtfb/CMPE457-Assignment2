# Image manipulation
#
# You'll need Python 2.7 and must install these packages:
#
#   numpy, PyOpenGL, Pillow

import sys, os, math

import numpy as np

from PIL import Image

from OpenGL.GLUT import *
from OpenGL.GL import *
from OpenGL.GLU import *


# Globals

windowWidth  = 1000 # window dimensions
windowHeight =  800

showMagnitude = True            # for the FT, show the magnitude.  Otherwise, show the phase
doHistoEq = False               # do histogram equalization on the FT

texID = None                    # for OpenGL

radius = 10                     # editing radius
editMode = 's'                  # editing mode: 'a' = additive; 's' = subtractive
zoom = 1.0                      # amount by which to zoom images
translate = (0.0,0.0)           # amount by which to translate images


# Image

imageDir      = 'images'
imageFilename = 'spitfire.jpg'
imagePath     = os.path.join( imageDir, imageFilename )

image    = None                   # the image as a 2D np.array
imageFT  = None                   # the image's FT as a 2D np.array

# Filter

filterDir      = 'filters'
filterFilename = 'gaussian7'
filterPath     = os.path.join( filterDir, filterFilename )

filter   = None                   # the filter as a 2D np.array
filterFT = None                   # the filter's FT as a 2D np.array


# Product of two FTs

product   = None
productFT = None


# File dialog

import Tkinter, tkFileDialog

root = Tkinter.Tk()
root.withdraw()

# Transpose a 2D numpy array
#
# Input is a 2D array of complex values
# Output is the same 2D array with rows and columns swapped

def Transpose (image):
  
  #calculate dimensions of image, and swap
  dim = (image.shape[1], image.shape[0])
  #create 2D array of zeros
  transposed = np.zeros(dim,dtype = np.complex128)
  col_count = 0
  for row in image:
    transposed[:,col_count] = row
    col_count+=1
  
  return transposed

# 1D FT
#
# You may use this code in your own forwardFT() and backwardFT() functions.


def ft1D( signal ):

  return np.fft.fft( signal )


# Do a forward FT
#
# Input is a 2D numpy array of complex values.
# Output is the same.

def forwardFT( image ):

  #initalize 2D output array of zeros
  dim = (image.shape[0],image.shape[1])
  output = np.zeros(dim,dtype=np.complex128)
  #set iterator for FFT on rows
  row_count = 0
  ##compute FFT for rows of image
  for row in image:
    output[row_count,:] = ft1D(row)
    row_count+=1
  
  col_count = 0
  #perform tranposition on 2D array in order to iterate over columns
  transposed = Transpose(output)
  ##compute FFT for columns of image
  for column in transposed:
    output[:,col_count] = ft1D(column)
    col_count+=1
    
  #return np.fft.fft2( image )
  print "computing FFT"
  return output


# Do an inverse FT
#
# Input is a 2D numpy array of complex values.
# Output is the same.


def inverseFT( image ):
  #The inverse FFT can be calculated by computing the FFT of the FFT of the image
  
  #initalize 2D output array of zeros
  dim = (image.shape[0],image.shape[1])
  temp = np.zeros(dim,dtype=np.complex128)
  output = np.zeros(dim,dtype=np.complex128)
  #set iterator for FFT on rows
  row_count = 0
  #take conjugate of elements in array
  temp = np.conjugate(image)
  ##compute FFT for rows of image
  ##according to https://docs.scipy.org/doc/numpy-1.13.0/reference/routines.fft.html
  ##direct FFT is not scaled so therefore inverse must be scaled by 1/N
  for row in temp:
    output[row_count,:] = ft1D(row/image.shape[0])
    row_count+=1
  
  col_count = 0
  ##Compute size of image array
  N = image.shape[0]*image.shape[1]
  #perform tranposition on 2D array in order to iterate over columns
  transposed = Transpose(output)
  ##compute FFT for columns of image
  ##according to https://docs.scipy.org/doc/numpy-1.13.0/reference/routines.fft.html
  ##direct FFT is not scaled so therefore inverse must be scaled by 1/N
  for column in transposed:
    output[:,col_count] = ft1D(column/image.shape[1])
    col_count+=1

  output = np.conjugate(output)
  print "computing IFFT"
  return output
  #return np.fft.ifft2( image )


# Multiply two FTs
#
# But ... the filter must first be shifted left and down by half the
# width and half the height, since the (0,0) of the filter should be
# in the "bottom-left corner", not in the image centre.
#
# To do this, first multiply the filter by e^{2 pi i x (N/2)/N} for
# width N and by e^{2 pi i y (M/2)/M} for height M.


def multiplyFTs( image, filter ):
  
  #initalize 2D output array of zeros
  #assume image and filter have same dimensions
  dim = (image.shape[0],image.shape[1])
  output = np.zeros(dim,dtype=np.complex128)

  #Iterate over the filter in order to shift left and down according to the comment above
  for r in range(image.shape[0]):
    for c in range(image.shape[1]):
      #use eulers formula to split complex exponentional ((simplified) as N/M cancel each other out) into real and imaginary parts
      mult = complex(math.cos(math.pi*(r+c)),math.sin(math.pi*(r+c)))
      output[r][c] = filter[r][c]*mult*image[r][c]
  #leave this alone
  print "computing filter multiplication"
  return output



# Set up the display and draw the current image


def display():

  # Clear window

  glClearColor ( 1, 1, 1, 0 )
  glClear( GL_COLOR_BUFFER_BIT )

  glMatrixMode( GL_PROJECTION )
  glLoadIdentity()

  glMatrixMode( GL_MODELVIEW )
  glLoadIdentity()
  glOrtho( 0, windowWidth, 0, windowHeight, 0, 1 )
  
  # Images to draw, in rows and columns

  toDraw, rows, cols, maxHeight, maxWidth, scale, horizSpacing, vertSpacing = getImagesInfo()

  for r in range(rows):
    for c in range(cols):
      if toDraw[r][c] is not None:

        if r == 0: # normal image
          img = toDraw[r][c]
        else: # FT
          img = np.fft.fftshift( toDraw[r][c] ) # shift FT so that origin is in centre (just for display)

        height = scale * img.shape[0]
        width  = scale * img.shape[1]

        # Find lower-left corner

        baseX = (horizSpacing + maxWidth ) * c + horizSpacing
        baseY = (vertSpacing  + maxHeight) * (rows-1-r) + vertSpacing

        # Get pixels and draw

        if r == 0: # for images, show the real part of each pixel
          show = np.real(img)
        else: # for FT, show magnitude or phase
          ak =  2 * np.real(img)
          bk = -2 * np.imag(img)
          if showMagnitude:
            show = np.log( 1 + np.sqrt( ak*ak + bk*bk ) ) # take the log because there are a few very large values (e.g. the DC component)
          else:
            show = np.arctan2( -1 * bk, ak )

          if doHistoEq and r > 0:
            show = histoEq( show ) # optionally, perform histogram equalization on FT image (but this takes time!)

        # Put the image into a texture, then draw it

        max = show.max()
        min = show.min()
        if max == min:
          max = min+1
          
        imgData = np.array( (np.ravel(show) - min) / (max - min) * 255, np.uint8 )

        glBindTexture( GL_TEXTURE_2D, texID )
        glTexImage2D( GL_TEXTURE_2D, 0, GL_INTENSITY, img.shape[1], img.shape[0], 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, imgData )

        # Include zoom and translate

        cx     = 0.5 - translate[0]/width
        cy     = 0.5 - translate[1]/height
        offset = 0.5 / zoom

        glEnable( GL_TEXTURE_2D )

        glBegin( GL_QUADS )
        glTexCoord2f( cx-offset, cy-offset )
        glVertex2f( baseX, baseY )
        glTexCoord2f( cx+offset, cy-offset )
        glVertex2f( baseX+width, baseY )
        glTexCoord2f( cx+offset, cy+offset )
        glVertex2f( baseX+width, baseY+height )
        glTexCoord2f( cx-offset, cy+offset )
        glVertex2f( baseX, baseY+height )
        glEnd()

        glDisable( GL_TEXTURE_2D )

        if zoom != 1 or translate != (0,0):
          glColor3f( 0.8, 0.8, 0.8 )
          glBegin( GL_LINE_LOOP )
          glVertex2f( baseX, baseY )
          glVertex2f( baseX+width, baseY )
          glVertex2f( baseX+width, baseY+height )
          glVertex2f( baseX, baseY+height )
          glEnd()

  # Draw image captions

  glColor3f( 0.2, 0.5, 0.7 )
 
  if image is not None:
    baseX = horizSpacing
    baseY = (vertSpacing  + maxHeight) * (rows) + 8
    drawText( baseX, baseY, imageFilename )

  if imageFT is not None:
    baseX = horizSpacing
    baseY = (vertSpacing  + maxHeight) * (rows-2) + vertSpacing - 18
    drawText( baseX, baseY, 'FT of %s' % imageFilename )

  if filter is not None:
    baseX = (horizSpacing + maxWidth) * 1 + horizSpacing
    baseY = (vertSpacing  + maxHeight) * rows + 8
    drawText( baseX, baseY, filterFilename )

  if filterFT is not None:
    baseX = (horizSpacing + maxWidth) * 1 + horizSpacing
    baseY = (vertSpacing  + maxHeight) * (rows-2) + vertSpacing - 18
    drawText( baseX, baseY, 'FT of %s' % filterFilename )

  if product is not None:
    baseX = (horizSpacing + maxWidth) * 2 + horizSpacing
    baseY = (vertSpacing  + maxHeight) * (rows) + 8
    drawText( baseX, baseY, "inverse FT of product of FTs" )
    
  if productFT is not None:
    baseX = (horizSpacing + maxWidth) * 2 + horizSpacing
    baseY = (vertSpacing  + maxHeight) * (rows-2) + vertSpacing - 18
    drawText( baseX, baseY, "product of FTs" )

  # Draw mode information

  str = 'show %s, %s edits' % (('magnitudes' if showMagnitude else 'phases'),
                               ('subtractive' if (editMode == 's') else 'additive'))
  glColor3f( 0.5, 0.2, 0.4 )
  drawText( windowWidth-len(str)*8-8, 12, str )

  # Done

  glutSwapBuffers()

  

# Get information about how to place the images.
#
# toDraw                       2D array of complex images 
# rows, cols                   rows and columns in array
# maxHeight, maxWidth          max height and width of images
# scale                        amount by which to scale images
# horizSpacing, vertSpacing    spacing between images


def getImagesInfo():

  toDraw = [ [ image,   filter,   product   ],
             [ imageFT, filterFT, productFT ] ]

  rows = len(toDraw)
  cols = len(toDraw[0])

  # Find max image dimensions

  maxHeight = 0
  maxWidth  = 0
  
  for row in toDraw:
    for img in row:
      if img is not None:
        if img.shape[0] > maxHeight:
          maxHeight = img.shape[0]
        if img.shape[1] > maxWidth:
          maxWidth = img.shape[1]

  # Scale everything to fit in the window

  minSpacing = 30 # minimum spacing between images

  scaleX = (windowWidth  - (cols+1)*minSpacing) / float(maxWidth  * cols)
  scaleY = (windowHeight - (rows+1)*minSpacing) / float(maxHeight * rows)

  if scaleX < scaleY:
    scale = scaleX
  else:
    scale = scaleY

  maxWidth  = scale * maxWidth
  maxHeight = scale * maxHeight

  # Draw each image

  horizSpacing = (windowWidth-cols*maxWidth)/(cols+1)
  vertSpacing  = (windowHeight-rows*maxHeight)/(rows+1)

  return toDraw, rows, cols, maxHeight, maxWidth, scale, horizSpacing, vertSpacing
  

  
# Equalize the image histogram

def histoEq( pixels ):

  # build histogram

  h = [0] * 256 # counts

  width  = pixels.shape[0]
  height = pixels.shape[1]

  min = pixels.min()
  max = pixels.max()
  if max == min:
    max = min+1

  for i in range(width):
    for j in range(height):
      y = int( (pixels[i,j] - min) / (max-min) * 255 )
      h[y] = h[y] + 1

  # Build T[r] = s

  k = 256.0 / float(width * height) # common factor applied to all entries

  T = [0] * 256 # lookup table
  
  sum = 0
  for i in range(256):
    sum = sum + h[i]
    T[i] = int( math.floor(k * sum) - 1 )
    if T[i] < 0:
      T[i] = 0

  # Apply T[r]

  result = np.empty( pixels.shape )

  for i in range(width):
    for j in range(height):
      y = int( (pixels[i,j] - min) / (max - min) * 255 )
      result[i,j] = T[y]

  return result
  

# Handle keyboard input

def keyboard( key, x, y ):

  global image, filter, product, showMagnitude, doHistoEq, productFT, filterFT, imageFT, imageFilename, filterFilename, filterPath, radius, editMode, zoom, translate

  if key == '\033': # ESC = exit
    sys.exit(0)

  elif key == 'I':

    imagePath = tkFileDialog.askopenfilename( initialdir = imageDir )
    if imagePath:
      image = loadImage( imagePath )
      imageFilename = os.path.basename( imagePath )
      imageFT = None

    if filterPath: # reload the filter so that it's resized to match the image
      filter = loadFilter( filterPath )
      filterFT = None

    product = None # clear the product
    productFT = None

  elif key == 'F':
    
    filterPath = tkFileDialog.askopenfilename( initialdir = filterDir )
    if filterPath:
      filter = loadFilter( filterPath )
      filterFilename = os.path.basename( filterPath )
    else:
      filter = None
    filterFT = None
      
    product = None # clear the product
    productFT = None

  elif key == 'm':
    showMagnitude = not showMagnitude

  elif key == 'h':
    doHistoEq = not doHistoEq

  elif key == 'x' and filterFT is not None and imageFT is not None:
    productFT = multiplyFTs( imageFT, filterFT )

  elif key == '+' or key == '=':
    radius = radius + 2
    print 'radius', radius

  elif key == '-' or key == '_':
    radius = radius - 2
    if radius < 2:
      radius = 2
    print 'radius', radius

  elif key in ['a','s']:
    editMode = key
    print editMode

  elif key == 'z':
    zoom = 1
    translate = (0,0)

  else:
    print '''keys:
           m  toggle between magnitude and phase in the FT  
           h  toggle histogram equalization in the FT  
           I  load image
           F  load filter
           x  multiply Fourier transforms
           +  increase editing radius
           -  decrease editing radius
  down arrow  forward transform
    up arrow  inverse transform

              translate with left mouse dragging
              zoom with right mouse draggin up/down
           z  reset the translation and zoom'''

  glutPostRedisplay()


# Handle special key (e.g. arrows) input

def special( key, x, y ):

  if key == GLUT_KEY_DOWN:
    forwardFT_all()

  elif key == GLUT_KEY_UP:
    inverseFT_all()

  glutPostRedisplay()



# Do a forward FT to all images


def forwardFT_all():

  global image, filter, product, imageFT, filterFT, productFT

  if image is not None:
    imageFT = forwardFT( image )
  if filter is not None:
    filterFT = forwardFT( filter )
  if product is not None:
    productFT = forwardFT( product )



# Do an inverse FT to all image FTs


def inverseFT_all():

  global image, filter, product, imageFT, filterFT, productFT

  if image is not None: 
    image = inverseFT( imageFT )
  if filter is not None:
    filter = inverseFT( filterFT )
  if productFT is not None:
    product = inverseFT( productFT )

    
# Load an image
#
# Return the image as a 2D numpy array of complex_ values.


def loadImage( path ):

  try:
    img = Image.open( path ).convert( 'L' ).transpose( Image.FLIP_TOP_BOTTOM )
  except:
    print 'Failed to load image %s' % path
    sys.exit(1)

  return np.array( list( img.getdata() ), np.complex_ ).reshape( (img.size[1],img.size[0]) )



# Load a filter
#
# Return the filter as a 2D numpy array of complete_ values.


def loadFilter( path ):

  try:
    with open( path, 'r' ) as f:

      line = f.readline().split()
      xdim = int(line[0])
      ydim = int(line[1])

      line = f.readline()
      scale = float(line)

      kernel = []

      for i in range(ydim):
        for x in f.readline().split():
          kernel.append( scale*float(x) ) # apply scaling factor here
  except:
    print 'Failed to load filter %s' % path
    sys.exit(1)

  # Place the kernel at the centre of an array with the same dimensions as the image.

  if image is None:
    result = np.zeros( (ydim,xdim) ) # only a kernel
  else:
    result = np.zeros( (image.shape[0], image.shape[1]) )

  cy = result.shape[0]/2 - ydim/2
  cx = result.shape[1]/2 - xdim/2 

  for y in range(ydim):
    for x in range(xdim):
      result[y+cy,x+cx] = kernel.pop(0) # image is indexed as row,column
      
  return result



# Handle window reshape

def reshape( newWidth, newHeight ):

  global windowWidth, windowHeight

  windowWidth  = newWidth
  windowHeight = newHeight

  glViewport( 0, 0, windowWidth, windowHeight )

  glutPostRedisplay()



# Output an image
#
# The image has complex values, so output either the magnitudes or the
# phases, according to the 'outputMagnitudes' parameter.

def outputImage( image, filename, outputMagnitudes, isFT ):

  if not isFT:
    show = np.real(image)
  else:
    ak =  2 * np.real(image)
    bk = -2 * np.imag(image)
    if outputMagnitudes:
      show = np.log( 1 + np.sqrt( ak*ak + bk*bk ) ) # take the log because there are a few very large values (e.g. the DC component)
    else:
      show = np.arctan2( -1 * bk, ak )
    show = np.fft.fftshift( show ) # shift FT so that origin is in centre

  min = show.min()
  max = show.max()

  img = Image.fromarray( np.uint8( (show - min) * (255 / (max-min)) ) ).transpose( Image.FLIP_TOP_BOTTOM )

  img.save( filename )




# Draw text in window

def drawText( x, y, text ):

  glRasterPos( x, y )
  for ch in text:
    glutBitmapCharacter( GLUT_BITMAP_8_BY_13, ord(ch) )

    

# Handle mouse click


currentButton = None
initX = 0
initY = 0
initZoom = 0
initTranslate = (0,0)

def mouse( button, state, x, y ):

  global currentButton, initX, initY, initZoom, initTranslate

  if state == GLUT_DOWN:

    currentButton = button
    initX = x
    initY = y
    initZoom = zoom
    initTranslate = translate

  elif state == GLUT_UP:

    currentButton = None

    if button == GLUT_LEFT_BUTTON and initX == x and initY == y: # Process a left click (with no dragging)

      # Find which image the click is in

      toDraw, rows, cols, maxHeight, maxWidth, scale, horizSpacing, vertSpacing = getImagesInfo()

      row = (y-vertSpacing ) / float(maxHeight+vertSpacing)
      col = (x-horizSpacing) / float(maxWidth+horizSpacing)

      if row < 0 or row-math.floor(row) > maxHeight/(maxHeight+vertSpacing):
        return

      if col < 0 or col-math.floor(col) > maxWidth/(maxWidth+horizSpacing):
        return

      # Get the image

      image = toDraw[ int(row) ][ int(col) ]

      if image is None:
        return

      # Find pixel within image

      pixelX = int((col-math.floor(col)) / (maxWidth /float(maxWidth +horizSpacing)) * image.shape[1])
      pixelY = image.shape[0] - 1 - int((row-math.floor(row)) / (maxHeight/float(maxHeight+vertSpacing )) * image.shape[0])

      # for the FT images, move the position half up and half right,
      # since the image is displayed with that shift, while the FT array
      # stores the unshifted values.

      isFT = (int(row) == 1)

      if isFT:
        pixelX = pixelX - image.shape[1]/2
        if pixelX < 0:
          pixelX = pixelX + image.shape[1]
        pixelY = pixelY - image.shape[0]/2
        if pixelY < 0:
          pixelY = pixelY + image.shape[0]

      # Perform the operation

      modulatePixels( image, pixelX, pixelY, isFT )

      #print 'click at', pixelX, pixelY

      # Done

      glutPostRedisplay()



# Handle mouse dragging
#
# Zoom out/in with right button dragging up/down.
# Translate with left button dragging.


def mouseMotion( x, y ):

  global zoom, translate

  if currentButton == GLUT_RIGHT_BUTTON:

    # zoom

    factor = 1 # controls the zoom rate
    
    if y > initY: # zoom in
      zoom = initZoom * (1 + factor*(y-initY)/float(windowHeight))
    else: # zoom out
      zoom = initZoom / (1 + factor*(initY-y)/float(windowHeight))

  elif currentButton == GLUT_LEFT_BUTTON:

    # translate

    translate = ( initTranslate[0] + (x-initX)/zoom, initTranslate[1] + (initY-y)/zoom )

  glutPostRedisplay()


# Modulate the image pixels within a given radius around (x,y).
#
# For subtractive edits (editMode == 's'), do this by multiplying the
# image values by one minus a Gaussian that has a standard deviation
# of half the radius.
#
# For additive edits (editMode == 'a'), do this by multiplying the
# image values by one plus 0.1 of the same Gaussian.
#
# Use image[y][x] since the images are indexed as [row,column].
#
# For FT images, the displayed FT image is really the log of the FT.
# So first take the log of the image value, apply the factor, then
# store the exp of the result.
#
# Also, FT images are symmetric around the origin, so a change at
# image[y][x] should also be made at image[-y][-x], which is really
# stored in image[ydim-1-y][xdim-1-x].


def modulatePixels( image, x, y, isFT ):
  
  print "x: " + str(x) + ", y: " + str(y)
  #print "radius: " + str(radius)
  
  #calculate row and column variables in order to iterate only on pixels within the square formed by the length radius around the clicked pixel
  #set row index
  row_start = y - radius
  if (row_start < 0):
    row_start = 0
  row_end = y + radius
  if (row_end > image.shape[1]):
    row_end = image.shape[1]
  #set column index
  col_start = x - radius
  if (col_start < 0):
    col_start = 0
  col_end = x + radius
  if (col_end > image.shape[0]):
    col_end = image.shape[0]
  
  #print "iterate from x: " + str(row_start) + "-" + str(row_end)
  #print "iterate from y: " + str(col_start) + "-" + str(col_end)
  
  stdDev = (radius/2) #standard deviation
  A = 1 #amplitude
  #iterates over circle at the location of the mouse click of size radius
  for row in range(row_start,row_end):
    for col in range(col_start,col_end):
      #check if current pixel is within the radius of the clicked pixel
      if ( math.sqrt( (row-(row_start+row_end)/2)**2 + (col-(col_start+col_end)/2)**2 ) <=radius):
        #calculate the gaussian
        gaussian = A * math.exp( -1 * ( ( (row-y)**2 ) + ( (col-x)**2 ) )/ (2*stdDev**2) )
        if (editMode == 's'): #subtractive mode
          if (isFT):
            #split the image value into real and imaginary parts
            real = np.real(image[row][col])
            imag = np.imag(image[row][col])
            
            #if the value is less than zero, log throws a math domain error, therefore switch to positive, apply transform, and switch back to negative
            if (real < 0):
              real = -1*real
              real = math.exp( math.log(real) * (1 - gaussian) )
              real = -1*real
            else:
              real = math.exp( math.log(real) * (1 - gaussian) )
            if (imag < 0):
              imag = -1*imag
              imag = math.exp( math.log(imag) * (1 - gaussian) )
              imag = -1*imag
            else:
              imag = math.exp( math.log(imag) * (1 - gaussian) )
              
            #apply to current pixel and mirror of pixel in image
            image[row][col] = real + 1j * imag
            image[image.shape[0]-1-row][image.shape[1]-1-col] = real + 1j * imag
             
          else:
            #otherwise, just apply gaussian normally
            image[row][col] = image[row][col] * ( 1 - gaussian )
            
        if (editMode == 'a'): #additive mode
          if (isFT): 
            #see comments made for subtractive mode
            real = np.real(image[row][col])
            imag = np.imag(image[row][col])
            
            if (real < 0):
              real = -1*real
              real = math.exp( math.log(real) * (1 + 0.1 * gaussian) )
              real = -1*real
            else:
              real = math.exp( math.log(real) * (1 + 0.1 * gaussian) )
            if (imag < 0):
              imag = -1*imag
              imag = math.exp( math.log(imag) * (1 + 0.1 * gaussian) )
              imag = -1*imag
            else:
              imag = math.exp( math.log(imag) * (1 + 0.1 * gaussian) )
 
            image[row][col] = real + 1j * imag
            image[image.shape[0]-1-row][image.shape[1]-1-col] = real + 1j * imag
        
          else:
            image[row][col] = image[row][col] * ( 1 + 0.1 * gaussian )

  pass



# For an image coordinate, if it's < 0 or >= max, wrap the coorindate
# around so that it's in the range [0,max-1].  This is useful in the
# modulatePixels() function when dealing with FT images.

def wrap( val, max ):

  if val < 0:
    return val+max
  elif val >= max:
    return val-max
  else:
    return val



# Load initial data
#
# The command line (stored in sys.argv) could have:
#
#     main.py {image filename} {filter filename}

if len(sys.argv) > 1:
  imageFilename = sys.argv[1]
  imagePath = os.path.join( imageDir,  imageFilename  )

if len(sys.argv) > 2:
  filterFilename = sys.argv[2]
  filterPath = os.path.join( filterDir, filterFilename )

image  = loadImage(  imagePath  )
filter = loadFilter( filterPath )


# If commands exist on the command line (i.e. there are more than two
# arguments), process each command, then exit.  Otherwise, go into
# interactive mode.

if len(sys.argv) > 3:

  outputMagnitudes = True

  # process commands

  cmds = sys.argv[3:]

  while len(cmds) > 0:
    cmd = cmds.pop(0)
    if cmd == 'f':
      forwardFT_all()
    elif cmd == 'i':
      inverseFT_all()
    elif cmd == 'm':
      outputMagnitudes = True
    elif cmd == 'p':
      outputMagnitudes = False
    elif cmd == 'x':
      productFT = multiplyFTs( imageFT, filterFT )
    elif cmd[0] in ['o','e']: # image name follows first letter
      sources = { 'i': image, 'ift': imageFT, 'f': filter, 'fft': filterFT, 'p': product, 'pft': productFT }
      isFT    = { 'i': False, 'ift': True,    'f': False,  'fft': True,     'p': False,   'pft': True      }
      if cmd[0] == 'o':
        filename = cmds.pop(0)
        outputImage( sources[cmd[1:]], filename, outputMagnitudes, isFT[cmd[1:]] )
      elif cmd[0] == 'e':
        x = int(cmds.pop(0))
        y = int(cmds.pop(0))
        modulatePixels( sources[cmd[1:]], x, y, isFT[cmd[1:]] )
    elif cmd == 'a':
      editMode = 'a'
    elif cmd == 's':
      editMode = 's'
    elif cmd == 'r':
      radius = int(cmds.pop(0))
    else:
      print """command '%s' not understood.
command-line arguments:
  f - apply forward FT
  i - apply inverse FT
  x - multiply FTs
  o - output an image: oi = image, oift = image FT, of = filter, offt = filter FT, op = product, opft = product FT
  r - set editing radius like 'r 10'    
  a - additive editing mode
  s - subtractive editing mode
  e - edit at a position like 'exxx 20 40' where exxx is one of ei, eift, of, offt, op opft (as with the 'o' command)
  m - for output, use magnitudes (default)
  p - for output, use phases""" % cmd

else:
      
  texID = glGenTextures(1)

  # Run OpenGL

  glutInit()
  glutInitDisplayMode( GLUT_DOUBLE | GLUT_RGB )
  glutInitWindowSize( windowWidth, windowHeight )
  glutInitWindowPosition( 50, 50 )

  glutCreateWindow( 'imaging' )

  glutDisplayFunc( display )
  glutKeyboardFunc( keyboard )
  glutSpecialFunc( special )
  glutReshapeFunc( reshape )
  glutMouseFunc( mouse )
  glutMotionFunc( mouseMotion )

  glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE)
  glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
  glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)
  glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
  glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
  glTexParameterfv(GL_TEXTURE_2D, GL_TEXTURE_BORDER_COLOR, [1,0,0,1] );

  glEnable( GL_TEXTURE_2D )
  glDisable( GL_DEPTH_TEST )

  glutMainLoop()
