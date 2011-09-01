#!/usr/bin/python 
# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
#    This file is part of 3d Brain Atlas Reconstructor                        #
#                                                                             #
#    Copyright (C) 2010-2011 Piotr Majka, Jakub M. Kowalski                   #
#                                                                             #
#    3d Brain Atlas Reconstructor is free software: you can redistribute      #
#    it and/or modify it under the terms of the GNU General Public License    #
#    as published by the Free Software Foundation, either version 3 of        #
#    the License, or (at your option) any later version.                      #
#                                                                             #
#    3d Brain Atlas Reconstructor is distributed in the hope that it          #
#    will be useful, but WITHOUT ANY WARRANTY; without even the implied       #
#    warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.         #
#    See the GNU General Public License for more details.                     #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along  with  3d  Brain  Atlas  Reconstructor.   If  not,  see            #
#    http://www.gnu.org/licenses/.                                            #
#                                                                             #
###############################################################################

"""
Module intened to process raw SVG files (generated by converting one page of PDF file to SVG
format) to 'pretraced' SVG file. Mainly, this porcess contains following steps:

    1. Read bregma coordinate,
    2. Calculate transformation to stereotaxic coordinate system,
    3. Store extracted data as SVG metedata.

More detailed information is provied in docstrings of particular functions.

G{importgraph}                                                                                      
"""

import commands #os
import re
import xml.dom.minidom as dom
import numpy as np
import sys
from string import *
from config import *
from math import sqrt

def find_bregma(svgdoc):
    """
    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document.
    @return      : Float value of bregma coordinate.

    Finds bregma coordinate by iterating over text objects
    and appyling regular expression.
    """
    #Iterate over text nodes looking for correct bregma expresion
    for el in svgdoc.getElementsByTagName('text'): 
        #Try to match regexp to current text node
        BregmaValueText=re_bregma.search(el.firstChild.nodeValue)
        if BregmaValueText:
            return float(BregmaValueText.group(1))

def _FindExtremeLabels(svgdoc):
    """
    Finds text labes which are:
         1. topmost (to find stereotaxic x coordinates and x resolution)
         2. rightmost (to find stereotaxic y coordinate and y resolution)

    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document.

    @requires: All topmost labels has the same y coordinate.
    @requires: All rightmost labels has the same x coordinate.
    @return  : Function returns preety complex date structure: C{([yCoordList,xCoordList],TextNodes)} where:
               1. yCoordList - sorted list of extracted stereotaxic y coordinates.
               2. xCoordList - sorted list of extracted stereotaxic x coordinates.
               3. TextNodes - list of all text objects in svg file: (x,y,text)

    @note: image x axis is left->right and (fortunately)
           stereotaxic x axis is also left->right.
    @note: image y axis is bottom->up while (unfortuantely)
           stereotaxic y axis is top->down.
    """

    # Gather coordinates and values of all text nodes:
    TextNodes=[];
    for el in svgdoc.getElementsByTagName('text'):
        # There are few labels that should be removed before initial parsing:
        if el.firstChild.nodeValue in CONF_PDF_HELPER_LABELS:
            el.parentNode.removeChild(el)
            continue
        # Then read getTextnodeData
        TextNodes.append(_getTextnodeData(el))
    
    # Select rigthmost coordinate wihin all text labels in file by selecting all text labels,
    # sorting them ascending by x coordinates and and taking first element of result.
    # RightMost - maximum x coordinate within all text labels.
    # Then we extract labels with x=RightMost - they enumerate y coordinates on the image.
    RightMost= max(map(lambda x: x[0], sorted(TextNodes,lambda x, y: int(x[0] - y[0]))))
    yCoordList= sorted([int(i[2]) for i in TextNodes if i[0]==RightMost])

    # The same with TopMost - maximum y coordinate,
    # xCoordList - values of labels which has y=TopMost.
    # Values enumerates stereotaxic x coordinates
    TopMost= min(map(lambda x: x[1], sorted(TextNodes,lambda x, y: int(x[1] - y[1]))))
    
    # Ok, because horizontal labels may (and probably would) be accidentaly merged,
    # We are going to merge them before...
    # We need to find all labels that have TopMost x coordinate and merge them into one label
    # after that we will split them and retrive separated digits.
    # Notice that this method works only when labels are single digits.
    
    # Selecting labels with x==TopMost
    xCoordList=[i[2] for i in TextNodes if i[1]==TopMost]
    #Join all labels and then split them by one char
    xCoordList=sorted(map(lambda x: int(x), "".join(xCoordList)))

    # yCoordList - sorted list of extracted stereotaxic y coordinates.
    # xCoordList - sorted list of extracted stereotaxic x coordinates.
    # TextNodes - list of all text objects in svg file: (x,y,text)
    return ([xCoordList,yCoordList],TextNodes)

def __isBrainLine(el):
    """
    @type  el: DOM object
    @param el: SVG element.

    Chcecks if given element may be considered as a component of brain structure.
    Function decides which element is "BrainLine" by comparing element's stroke color.
    """
    if el.hasAttribute('stroke') and el.getAttribute==CONFIG_BRAIN_LINE_STROKE:
        return True
    else:
        return False

def _convertToPolylines(el, svgdoc):
    """
    @type  el: DOM node object
    @param el: SVG polyline element.

    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document.

    Converts polyline element to serie of line elements preserving its coordinates (obvious)
    and stroke (not so obvious).
    """

    # Again, we use loop+buffer method:
    # Define empty buffer:
    buffer=""

    # Split "points" attribute vallue it order to get list of points
    PointsTable=split(el.attributes['points'].value)

    # The clue is that if given line belongs to brain structure it has to be converted
    # to path (with segments created from lines). Otherwise it shlould be broken into
    # separate line objects for arrow <-> structure matching.
    
    if __isBrainLine(el):
        for pt in PointsTable:
            # Extract pair of points from string and then 
            # convert results to list
            PtPair=list(re_PointsPair.search(pt).groups() )

            # Transform given point using provided transformation matrix
            # and convert results tuple of strings and update buffer string
            if buffer=="":
                buffer+="M%s,%s " % tuple(PtPair)
            else:
                buffer+="L%s,%s " % tuple(PtPair)

            # Create new line basing on given pair of points
        el.tagName='path'
        el.removeAttribute('points')

        el.setAttribute('d',buffer)
        el.setAttribute('stroke',CONFIG_BRAIN_LINE_STROKE)
    else:
        # Split lines into segments of two points
        # Extract list of coordinates in consecutive segments (c1,c2),(c2,c3),(c3,c4)...
        for pt in [PointsTable[i:i+2] for i in range(0, len(PointsTable)-1, 1)]:

            # Extract coordinates
            PtPair=map( lambda x: list(re_PointsPair.search(x).groups() ), pt)

            # Create new line element, apply black stroke and insert into DOM structure 
            newel=svgdoc.createElement('line')
            newel.setAttribute('x1',PtPair[0][0])
            newel.setAttribute('y1',PtPair[0][1])
            newel.setAttribute('x2',PtPair[1][0])
            newel.setAttribute('y2',PtPair[1][1])
            newel.setAttribute('stroke',CONFIG_BLACK_LINE_STROKE)
            el.parentNode.insertBefore(newel, el)

def _isGridLine(el):
    """
    @type  el: DOM object
    @param el: SVG element to test
    Tests wheter give element is gridline element.

    @return  : C{True} if given element is gridline
               (according to L{grid element definition<CONF_GRID_ELEMENT>}),
               false otherwise.
    """
    # TODO implement chekcing if element has mentioned attributes
    for test in CONF_GRID_ELEMENT:
        if el.attributes[test].value!=CONF_GRID_ELEMENT[test]: return False
    return True

def _getGridlines(svgdoc):
    """
    Extracts horizontal and vertical gridlines from whole SVG document.

    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document.

    @return      : List of image y coordinates of vertical grid,
                   liist of image x coordinates of horizontal grid:
                   C{[ycoords, xcoords]}
    """
    HorizontalGrid=[]
    VerticalGrid=[]

    for el in svgdoc.getElementsByTagName('line'):
        
        # Check if line is a grid element:
        if _isGridLine(el):
            # Criteria for horizontal grid
            # TODO Create separated horizontal grid function
            if el.attributes['y1'].value==el.attributes['y2'].value and\
                abs(float(el.attributes['x2'].value)-float(el.attributes['x1'].value))>CONF_GIRD_ELEMENT_MIN_LENGTH:
                HorizontalGrid.append(float(el.attributes['y1'].value))
                continue

            # Criteria for vertical grid
            # TODO Create separated vertical grid function
            if el.attributes['x1'].value==el.attributes['x2'].value and\
                abs(float(el.attributes['y2'].value)-float(el.attributes['y1'].value))>CONF_GIRD_ELEMENT_MIN_LENGTH:
                VerticalGrid.append(float(el.attributes['x1'].value))   

    #XXX very important!! Both girds lists has to be sorted ascending (smaller-->larger
    #XXX to avoid stupid errors
    HorizontalGrid.sort()
    VerticalGrid.sort()

    return [VerticalGrid,HorizontalGrid]

def getStereotacticTransformationMatrix(lines,labels):
    """
    @type  lines  : list
    @param lines  : List with gridlines created by L{_getGridlines<_getGridlines>}
    @type  labels : list
    @param labels : List of labels generated L{_FindExtremeLabels<_FindExtremeLabels>}
    @return       : Tuple of two tuples with x and y scale factor and ammount of translation.
                    C{((a,b),(c,d))}
    
    @requires: Number of elements in corresponding lines and labels elements should match.
    @note    : Calculating transformation matrix may fail, if some labels will be merged by converter (ie. pstoedit).
    @todo    : NumPy matrix should be returned instead of tuples.

    Calculates  x and y offsets and scales in order to transform coordinated
    to bregma coordinates system.

    This function requires few words of explanation:
    We assume that y coordinates (rigth scale on the image) are matching corresponding
    y (horizontal) gridlines one by one (ie. there are six labels and six gridlines).
    The same rule applies to x coordinates.
    """

    # XXX quick dirty patch
    # if there are two more vertical gridlines than vertical labels,
    # leave first and the last one gridline
    if len(lines[0])-2==len(labels[0]): lines[0]=lines[0][1:-1]

    # Chcecking if number of gridlines matches number of gridlabels
    if not all(map(lambda x,y: len(x)==len(y), lines,labels)):
        print "Number of gridlines do not match number of grid labels. Please check it."

    # names shortcuts
    g=map(float,lines[1])    # horizontal gridlines -> x coordinate
    l=map(float,labels[1])   # x gridlabels
    
    # if we know that "Image" axis is reversed in comparison with "stereotactical" Y axis,
    (a,b)=_calcScalingAndOffset(g,l)

    # names shortcuts
    g=map(float,lines[0])   # vertical gridlines -> y coordinate
    l=map(float,labels[0])  # y gridlabels

    (c,d)=_calcScalingAndOffset(g,l)

    #TODO NumPy matrix should be returned instead of tuples.
    return ((a,b),(c,d))

def _calcScalingAndOffset(g,l):
    """
    Calculates scaling factor and offsets for transforming coordinates from SVG coordinates
    to stereotaxic coordinates system. Matrix is computed basing on gridlines coordinates and
    values of provied labels.

    @type  g: list
    @param g: list of coordinates of gridlines

    @type  l: list
    @param l: list of values assigned to corresponding gridlines 

    @return: Tuple of two values C{(a,b)}, where C{a} is and scaling factor and C{b}
             - offset. Both values are obviously calculated from C{g} and C{l}.
    """
    
    # Check, if number of gridlines matches number of labels.
    if len(g)!=len(l):
        # if number of gridlines is different from number of labels
        # there is an obviously error! In such case return 1 as scaling factor
        # and 0 as offset.
        return (1,0)

    # Check if distance between lables values if exeactly one unit in every case:
    # if it is, differencing the list should give 1.
    # if not, we take extrame values n and create sequence (-n,...,0,...,)
    # and we get sequence of consecutive values
    if not all(map( lambda x,y: x-y==1, l[1:],l[:-1])):
        l=range(-int(max(l)),int(max(l))+1,1)

    # if labels are consecutive, it is easy to calculate scaling and translation
    # a=(y1-y2)/(x1-x2)
    # b=y1-a*x1
    a=(l[0]-l[1])/(g[0]-g[1])

    b=l[0]-a*g[0]
    return (a,b)

def _getTextnodeData(TextNode):
    """
    Extracts all information (x,y,text) from given text node.

    @type  TextNode: DOM object
    @param TextNode: Text SVG element to extract infomation from.

    @return: [x coord, y coord, text] 
    """
    #TODO: Make this function bulletproof (exception handling)
    return (\
        float(TextNode.attributes['x'].value),\
        float(TextNode.attributes['y'].value),\
        str(TextNode.firstChild.nodeValue)\
        )

# Now, set of functions for cleaning documents from unnecessary elements
# as thumbnail brain drawing,
# ticks, frames, gidlines etc.

def getArrowLength(el):
    """
    @type  el: DOM object                                                                        
    @param el: Line SVG element which length will be calculated.

    @return  : (float) length od the segment
    """
    x=map(lambda e: float(el.attributes[e].value), ['x1','x2','y1','y2'])
    return sqrt( (x[0]-x[1])**2 + (x[2]-x[3])**2)

def _isAxisTick(el):
    """
    @type  el: DOM object                                                                        
    @param el: Line SVG element which length will be calculated.

    @return: (boolean) C{True} if this element is tick, C{False} otherwise.

    Determined wether given element should be treaten as tick.
    In case of this atlas, ticks are elements which has the same attributes
    as girdlines, arrowlines. What's more, they length cannot exceed 4 units.
    """

    if not __isBrainLine(el) and  getArrowLength(el) < 4:
        return True
    else:
        return False

def _cleanSVG(svgdoc):
    """
    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document.

    @return: nothing, C{svgdoc} is modified in-place.

    Set of procedures which cleans SVG document from unwanted/redundant information.
    Removing of each kind of element is described precisely in source code.

    Short summary:
    
        1. Remove ticks (those small lines around the frame
        2. Remove polygons, polylines and rectangles as they cannot be parts of brain structure
        3. Remove paths which are not coloured like other brain parts
        4. Remove text elements which does not match brain structure label definition
        5. Remove gridlines as they are no longer necessary (as we have red scaling factor and offsets)
        6. Remove labels which are defined as 'not to trace labels'
    """
    # Take each line element and perform actions depending on line characteristics
    for el in svgdoc.getElementsByTagName('line'):

        # In this step we remove ticks. Ticks are small lines around the frame.
        # _isTick function is used to determine if given line element is tick.
        if _isAxisTick(el):
            el.parentNode.removeChild(el)

        # For all lines we remove dashing - all lines will be solid lines.
        # Is important especially to brain lines as we render them later 
        # and use them as a boundaries so they could not be dashed.
        if el.hasAttribute("stroke-dasharray"):
            el.removeAttribute("stroke-dasharray")

        # Thick lines - drawing frame, thumbnail frame
        # and some other lines: we need to remove them also
        # NOTE that we not delete lines which are brain lines
        if el.hasAttribute("stroke-width"):
            if el.getAttribute('stroke')==CONFIG_BRAIN_LINE_STROKE:
                continue
            else:
                temp= el.attributes['stroke-width'].value
                if temp in ['0.75','0.5']:
                    try:
                        el.parentNode.removeChild(el)
                    except:
                        continue

        # Last but not least - gridlined. As we already calculates offsets and scaling factors
        # (we know how to transform from drawing coordinates to stereotaxic coordinated)
        # we can delete grdlines
        if _isGridLine(el):
            el.parentNode.removeChild(el)

    # brain parts does not have polygons - remove them
    for el in svgdoc.getElementsByTagName('polygon'):
        el.parentNode.removeChild(el)
    
    # All polylines shout be converted to lines by this moment
    # thus removeing polylines is rather formality
    for el in svgdoc.getElementsByTagName('polyline'):
        _convertToPolylines(el,svgdoc)
        el.parentNode.removeChild(el)

    # Brain parts does not have rectangles either!
    for el in svgdoc.getElementsByTagName('rect'):
        el.parentNode.removeChild(el)

    # Removing all non brain paths
    for el in svgdoc.getElementsByTagName('path'):
        # All path that are which have colours the same as grid or arrowlines or ticks or whatever
        # are definetly not brain-paths. Remove them at once :)
        if el.hasAttribute("stroke") and\
            el.attributes['stroke'].value in [CONFIG_ARROW_LINE_STROKE, CONFIG_BLACK_LINE_STROKE]:
                el.parentNode.removeChild(el)

        # For all lines we remove dashing - all paths will be solid lines.
        # Is important especially to brain lines as we render them later 
        # and use them as a boundaries so they could not be dashed.
        if el.hasAttribute("stroke-dasharray"):
            el.removeAttribute("stroke-dasharray")

        # We also need to remove filling apply storke characteristic to brainline
        # =CONFIG_BRAIN_LINE_STROKE
        if el.hasAttribute("fill"):
            el.removeAttribute("fill")
            el.setAttribute('stroke',CONFIG_BRAIN_LINE_STROKE)
            el.setAttribute('stroke-width','0.5')

    for el in svgdoc.getElementsByTagName('text'):
        # Remove text elements which does not match brain structure label definition
        # There is no structure defined by label consisting with more than 7 charecters (pure heuristics :))
        if len( str(el.firstChild.nodeValue) ) >7 or el.attributes['font-size'].value in ['5px','6px','7px','8px','10px']:
            el.parentNode.removeChild(el)

        # Also remove labels which are declared as not to trace
        # Most probably we not want to trace them because they are outside the brain
        # and tracing them means tracing something which is not brain actually
        if str(el.firstChild.nodeValue) in CONF_STRUCTURES_NON_TRACE:
            el.parentNode.removeChild(el)

def _indexElements(svgdoc):
    """
    @type  svgdoc: DOM object
    @param svgdoc: Whole SVG document

    @return: none, only svgdom is modified in-place

    Assigns ID attribute to all text and path elements, assuming that
    they are only graphical objects in the file. We need to do that because
    SVG 1.1 specification requres uniqe id assigned to every object.
    """

    # Add indexes to text label:
    # TODO: This code is stupid rebuild it!!!
    TextIndex=0
    TextElementIDPrefix="label%d"
    
    PathIndex=0
    PathElementIDPrefix="path%d"

    for el in svgdoc.getElementsByTagName('text'):
        el.setAttribute('id', TextElementIDPrefix % TextIndex)
        TextIndex+=1

    for el in svgdoc.getElementsByTagName('path'):
        el.setAttribute('id', PathElementIDPrefix % PathIndex )
        PathIndex+=1

def _saveTransformationAsMetadata(svgdom, transformation, bregma):
    """
    @type  svgdom: DOM object
    @param svgdom: Whole SVG document

    @type  transformation: nested tuple
    @param transformation: drawing to stereotaxic coordinate system transformation matrix created by
             L{getStereotacticTransformationMatrix<getStereotacticTransformationMatrix>}.

    @type  bregma: double 
    @param bregma: bregma coordinate of given slide.

    Saves image to stereotectical coordinates transformation matrix as XML metadata.
    """

    # Search for SVG metadata as we do not want to overwrite existing metadata.
    svgElement=svgdom.getElementsByTagName('svg')[0]
    metadataElement=svgdom.getElementsByTagName('defs')

    # TODO: This code is stupid rebuild it!!!
    # if there is no metadata element, we need to create such
    if len(metadataElement)==0:
        metadataElement=svgdom.createElement('defs')
        svgElement.appendChild(metadataElement)
        svgElement.insertBefore(metadataElement, svgdom.getElementsByTagName('g')[0])
    metadataElement=svgdom.getElementsByTagName('defs')[0]
    # Ready, however this code is really stupid and requires immediate rewriting
    
    # Appending transformation matrix and bregma coordinate
    # TODO: Should be done better
    TransformationMatrix=svgdom.createElement('bar:data')
    TransformationMatrix.setAttribute('name','transformationmatrix')
    TransformationMatrix.setAttribute('content',\
            str(transformation[1][0])+','+\
            str(transformation[1][1])+','+\
            str(transformation[0][0])+','+\
            str(transformation[0][1]) )
    metadataElement.appendChild(TransformationMatrix)

    BregmaMetadataElement=svgdom.createElement('bar:data')
    BregmaMetadataElement.setAttribute('content',str(bregma))
    BregmaMetadataElement.setAttribute('name','coronalcoord')
    metadataElement.appendChild(BregmaMetadataElement)

def processFile(svgdom):
    """
    Performs all processing reated to cleaning and extracting data from SVG image:
    
        1. Read bregma coordinate
        2. Calculate transformation to stereotaxic coordinate system
        3. Stores extracted data as SVG metedata

    @type  svgdom: DOM object
    @param svgdom: Whole SVG document

    @return: (nested tuple): bregma coordinate calculated via L{find_bregma<find_bregma>}
             and stereotaxic transformation matrix calculated by
             L{getStereotacticTransformationMatrix<getStereotacticTransformationMatrix>}.
    """
    bregma=find_bregma(svgdom)

    # Only for debuging purposes
    if __debug__:   
        print >>sys.stderr, "Proccesing slide with bregma:\t%f" % bregma

    # Extract information about horizontal and vertical gridlines
    gridlines=_getGridlines(svgdom)
    print >>sys.stderr, "Searching for extreme labels"
    grid,Text=_FindExtremeLabels(svgdom)

    # Calculate stereotaxic transformation matrix
    # and store it as SVg metadata element
    transform=getStereotacticTransformationMatrix(gridlines,grid)
    _saveTransformationAsMetadata(svgdom,transform,bregma)

    # Clean file from unnecessary elements  
    _cleanSVG(svgdom)

    return (bregma,transform)

if __name__=='__main__':
    pass
