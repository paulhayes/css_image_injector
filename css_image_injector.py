#!/usr/bin/env python
"""
	Injects base64 encoded image data into css file
	author Paul Hayes
"""

import sys
import os
import re
import io
import base64
import cssutils
from cssutils import parseFile
from cssutils.css import CSSRule
from PIL import Image
from PIL import ImageOps
from string import Template

#Add CSS Profiles for browser prefixes

macros = { 
	'timingfunction':'linear|ease|ease-in|ease-out|ease-in-out|cubic-bezier\(\s*{number}\s*,\s*{number}\s*,\s*{number}\s*,\s*{number}\s*\)',
	'func':'(translate|scale)\(({number}|{length}|{percentage})(\s*,\s*{number}|{length}|{percentage})?\s*\)'
}

common = {
	'transform' : '({func}\s*){1,}',
	'transition' : '{ident}\s+{time}\s+{timingfunction}?',
	'transform-origin' : '({length}|{percentage}) ({length}|{percentage})',
}

cssutils.profile.addProfile('CSS3 Advanced', common, macros)
cssutils.profile.addProfile('Webkit Prefixes',{ '-webkit-%s' % k : common[k] for k in common }, macros)
cssutils.profile.addProfile('Moz Prefixes',{ '-moz-%s' % k : common[k] for k in common }, macros)
cssutils.profile.addProfile('O Prefixes',{ '-o-%s' % k : common[k] for k in common }, macros)
cssutils.profile.addProfile('IE Prefixes',{ '-ms-%s' % k : common[k] for k in common }, macros)



def css_inject_images(stylesheet,sourceDir):

	injectedImages = {}
	injectedImageNames = []

	index=0

	def get_val(val):
		return int( re.match(r'[\-0-9]+','%s' % val).group() )

	for rule in stylesheet.cssRules:
		if not rule.type == CSSRule.STYLE_RULE :
			continue

		style = rule.style
		backgroundImage = style.getPropertyValue('background-image', True)
		backgroundPosition = style.getPropertyValue('background-position', True)

		if not backgroundImage :
			background = style.getPropertyValue('background', True)
			backgroundProperties = background.split(' ')
			if len( backgroundProperties ) >= 3 and re.match( r"url\([^)]+\)", backgroundProperties[0] ) :
				backgroundImage = backgroundProperties[0]
				if "px" in backgroundProperties[1] and "px" in backgroundProperties[2] :
					backgroundPosition = tuple( -get_val(n) for n in backgroundProperties[1:3] )
				else:
					sys.exit('Unable to process background position properties, %s' % background )
			#print ', '.join( backgroundProperties )
			
		if backgroundImage : 
			backgroundImageURL = re.match( r"url\(([^)]+)\)", backgroundImage ).group(1)
			isPNG = ".png" in backgroundImageURL.lower()
			imagePath = os.path.realpath( os.path.join( sourceDir,backgroundImageURL ) )
			name = backgroundImageURL
			if not os.path.isfile( imagePath ) :
				sys.exit('Referenced image file not found %s ' % backgroundImageURL)

			image = Image.open(imagePath)

			#print '1. writing %s' % os.path.relpath( imagePath )
			#print '2. %d,%d'	% image.size

			if backgroundPosition:
				width = get_val( style.getPropertyValue("width") )
				height = get_val( style.getPropertyValue("height") )
				dimensions = image.size
				bounds = backgroundPosition + (width,height)
				#print("3. bounds %d,%d %d,%d,%d,%d " % ( bounds + (width,height) ) )
				borders = ( bounds[0],bounds[1],max( 0,dimensions[0]-bounds[2]-bounds[0] ), max( 0,dimensions[1]-bounds[3]-bounds[1]) );
				image = ImageOps.crop( image, borders )
				name = '%s,%d,%d,%d,%d'  % ( (backgroundImageURL,)+borders )
				#print( "4. cropping %d, %d, %d, %d" % borders )

			output = io.BytesIO()
			base64Output = io.BytesIO()

			format='png' if isPNG else 'jpeg'
			image.save( output, format=format.upper() )
			output.seek(0)
			base64.encode( output, base64Output )
			base64Output.seek(0)
			imageTemplatePlaceholder = 'url($image%d)' % index
			base64EncodedImage = '"data:image/%s;base64,%s"' % (format,base64Output.getvalue())
			injectedImages['image%d' % index] = base64EncodedImage
			index+=1
			base64Output.close()
			output.close()

			style.setProperty('background-image', imageTemplatePlaceholder )
			style.removeProperty('background-position',True)
			style.removeProperty('background',normalize=True)
			if name in injectedImageNames :
				sys.stderr.write('WARNING: Image already injected : %s' % name )
			else :
				injectedImageNames.append( name )

	return Template(stylesheet.cssText).safe_substitute( injectedImages )

def main():
	if len(sys.argv) < 3:
	    sys.exit('Usage: %s sourceFile outputFile' % sys.argv[0])

	css_file_inject_images(sys.argv[1],sys.argv[2])

def css_file_inject_images(infile,outfile):
	sourceDir = os.path.dirname( infile )
	sourceFile = os.path.basename( infile )
	outputFile = os.path.basename(outfile)
	outputDir = os.path.dirname(os.path.abspath( outfile ) )

	if not os.path.isdir(sourceDir):
	    sys.exit('ERROR: Source directory not found %s' % sourceDir )

	if not os.path.isfile( os.path.join( sourceDir, sourceFile ) ):
	    sys.exit('ERROR: Source file not found %s' % sourceFile )

	if not os.path.isdir(outputDir):
		sys.exit('ERROR: Output directory not found %s' % outputDir )

	stylesheet = parseFile( os.path.join( sourceDir, sourceFile ) )
	outputCSS = css_inject_images(stylesheet,sourceDir)

	out = open( os.path.join( outputDir, outputFile ), "w" )
	out.write( outputCSS )
	out.close()


if __name__ == '__main__':
	main()
