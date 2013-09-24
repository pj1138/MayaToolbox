#AUTORIG

import pymel.core as py
import maya.cmds as mc
import maya.mel as mel
from math import *
from xml.dom.minidom import *
from random import uniform as rnd
import os
import re
#~~
from general import *

# function to create a default bipedal skeleton
def createBipedSkeleton(prefix='', size=1.0):
   rootJnt = mc.joint(prefix+'_root_jnt', p=(0,15,0))
 
   # make other joints
 
   # orient skeleton
   orientBipedSkeleton(rootJnt)
 
   return rootJnt
 
# function to reorient the skeleton joints to "factory settings" so that the autorig maintains consistent orientations no matter the joint positions.
def orientBipedSkeleton(rootJnt = None):
   if not rootJnt:
      return False
 
   # orient rootJnt
   mc.joint(rootJnt, e=True, oj='xzy', secondaryAxisOrient='zup', zso=True)
 
   # find and orient the rest of the joints
 
   return True 

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Write a function that will build an IK/FK rig programmatically, given 3 joints as the input
# 1. Function should assume joints are oriented correctly
# 2. Process:
#   2.1. Duplicates the given joint heirarchy
#   2.2. Renames duplicate to have "_IK" suffix
#   2.3. Runs chain through IK setup function as written previously
#   2.4. Duplicates original chain
#   2.5. Renames duplicate to have "_FK" suffix
#   2.6. Runs chain through FK setup function as written previously
#   2.7. Create "Settings" curve and constrains it to the last skin joint
#   2.8. Add attribute to Settings curve for FK/IK switch
#   2.9. Constrains original joints to the FK/IK joints using parentConstraints
#   2.10. Link constraints up to FK/IK attribute on Settings controller
#   2.11. Cleans up nodes into a single grouped hierarchy, leaving the original chain intact.
# 3. return group

def fkikCreateController(startJoint=None, endJoint=None, name="controller"):
    name = getUniqueName(name)
    target = []

    print "startJoint: " + str(startJoint) + "   endJoint: " + str(endJoint)

    if not startJoint or not endJoint:
        target = s()
    else:
        firstList = mc.listRelatives([startJoint], ad=1)
        secondList = mc.listRelatives([endJoint], ad=1)
        target = []
        for i in range(0,len(firstList) - len(secondList)):
            target.append(firstList[i])
        target.append(startJoint)
        print "Specified start and end joints."
        print "Listing: " + target
    
    for i in range(0,len(target)):
        tempTarget = mc.listRelatives([target[i]], ad=1)
        tempTarget.append(target[i])
        print "0. tempTarget: " + str(tempTarget)
        origTarget = []
        for h in range(0,len(tempTarget)):
            origTarget.append(tempTarget[(len(tempTarget)-1)-h])
        print "1. origTarget: " + str(origTarget)

        name1 = getUniqueName(target[i]+"_IK")
        ikTarget = duplicateSpecial(name=name1)
        print "2. ikTarget: " + str(ikTarget)

        name2 = getUniqueName(target[i]+"_FK")
        fkTarget = duplicateSpecial(name=name2)
        print "3. fkTarget: " + str(fkTarget)

        name3 = getUniqueName(name)
        if not startJoint or not endJoint:
            startJoint = ikTarget[0]
            endJoint = ikTarget[len(target)-2]
        ikCreateControllerAlt(startJoint=startJoint, endJoint=endJoint, name=name3)
        
        name4 = getUniqueName(name)
        fkCreateController(fkTarget, name=name4)

        settings = controllerGeometry(controlType="star",size=2,name="settings")
        # ...if you want to rotate the star controller
        #mc.setAttr(settings + ".rotateX",90)
        #freezeTransformations(settings)
        pos = getPos([target[i]])
        mc.move(pos[0][0],pos[0][1],pos[0][2])
        # do later!
        #py.parentConstraint(settings,target[i],mo=1)
        fkikName = "FKIK_switch"
        fkik = addAttrFloatSlider([settings],name=fkikName)
        fkikVal = mc.getAttr(settings + "." + fkikName)
        print fkikVal

        for j in range(0,countChain(target[i])+1):
            pcfk = py.parentConstraint(fkTarget[j],origTarget[j])
            expr1 = "expressionEditor EE \""+pcfk+"\" \""+fkTarget[j]+"W0\";"
            print "expr1: " + expr1
            #expr2 = "expression -s \""+str(pcfk)+"."+str(fkTarget[j])+"W0 = "+str(settings)+"."+str(fkikName)+"\"  -o "+str(settings)+" -ae 1 -uc all ;"
            expr2 = "expression -s \""+pcfk+"."+fkTarget[j]+"W0 = abs(1-"+settings+"."+fkikName+")\"  -o "+settings+" -ae 1 -uc all ;"
            print "expr2: " + expr2
            mel.eval(expr1)
            mel.eval(expr2)
            #~~
            pcik = py.parentConstraint(ikTarget[j],origTarget[j])
            expr3 = "expressionEditor EE \""+pcik+"\" \""+ikTarget[j]+"W1\";"
            print "expr1: " + expr3
            expr4 = "expression -s \""+pcik+"."+ikTarget[j]+"W1 = "+settings+"."+fkikName+"\"  -o "+settings+" -ae 1 -uc all ;"
            print "expr2: " + expr4
            mel.eval(expr3)
            mel.eval(expr4)

        py.parentConstraint(settings,target[i],mo=1)
        name5 = getUniqueName(name)
        mc.group(settings,name1,name2,name3,name4,name=name5)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Write a function that will automatically create an IK setup, given a list of joints
# 
# 1. Assume joints are oriented correctly
# 2. Function should return base IK joint, control curves
# 3. Process:
#   3.1. Create ikHandle from base joint to end joint
#   3.2. Create cube control curve
#   3.3. snap controller_constraint to end joint
#   3.4. parent ikHandle to control curve
#   3.5. create pole vector controller (see constrain menu)
#   3.6. snap pole vector controller to middle joint *
#   3.7. create pole vector constraint to ikHandle
#   3.8. clean up all created objects into separate group
# 4. def createIKControls(startJoint, endJoint)
# 5. return [group, IK Controller, Pole Vector, IK Chain Base]
# 
# * Make the middle snap to the middle joint in any number of arbitrary joints. If there is an even number, 
# just pick the lowest of the 2 half joints. (ie: 3 joints, pole on 2nd, 4 joints - pole vector on 2nd. 
# 5 joints - pole vector on 3rd, 6 joints - pole on 3rd, etc.)

def ikCreateController(startJoint=None, endJoint=None, controlType="cube", size=1.0, name="controller"):
    name = getUniqueName(name)

    #getting rid of multiple targets
    if not startJoint:
        startJoint = mc.ls(sl=True)[0]

    joints = mc.listRelatives( startJoint, ad=True )
    
    # let's find our end joint
    if not endJoint:
        endJoint = joints[0]


    finalGroup = mc.group(em=True, name=name)

    appendCtl = "_control"
    appendCst = "_constraint"
    appendGrp = "_group"
    appendPole = "_pole"

    returns = []

    # getting rid of loop, since the only time this loop will run
    # is if you want to select multiple start joints and have multiple
    # ik controls being made with a single command. It's better to keep
    # the scope of this function limited at this point and if you want
    # to create multiple ik controllers, create another function that
    # will call this one based off multiple selection

    #for i in range(0,len(target)):

    '''
    #2. Create IK handle
    if not startJoint or not endJoint:
        mc.select(target[i])
        joints = mc.listRelatives(ad=True)
        joints.append(target[i])
        mc.select(joints[len(joints)-1],joints[0])
    else:
        mc.select(startJoint)
        joints = mc.listRelatives(ad=True)
        joints.append(startJoint)
        mc.select(startJoint,endJoint)
    '''

    # directly inputting the start joint and end effector
    print startJoint[0]
    print endJoint
    handle = py.ikHandle(sj=startJoint[0], ee=endJoint, solver="ikRPsolver")
    
    #3. Create controller
    ctl = controllerGeometry(controlType,size, getUniqueName(name), appendCtl) # getting unique name now
    ctl2 = controllerGeometry("sphere",size, getUniqueName(name+appendPole), appendCtl) # getting unique name now
    
    # got rid of conditional
    '''
    if not startJoint or not endJoint:
        snapToPos([ctl,joints[0]])
    else:
    '''
    snapToPos([ctl,endJoint[0]])
    
    #~~
    # got rid of selection, directly inputting what to group
    ctlGrp = [mc.group(ctl, n= getUniqueName(name + appendGrp))]
    ctlCst = [mc.group(ctlGrp, n= getUniqueName(name + appendCst))]

    #~~
    mc.parent(handle[0],ctlGrp[0])
    middleJoint = 0;
    
    # at this point startJoint and endJoint are definitely going to be there.
    # we don't want to create too many similar conditionals and reuse code.
    # It's better to just create a function that tries to fill in the information,
    # for instance in this case, the function needs a start joint and an end joint,
    # so you should use selection in the beginning to get your start and end joint
    # instead of creating a number of conditionals to do different things at different
    # times. These branches could lead to bugs.
    '''
    if not startJoint or not endJoint:
        jointCount = countChain(target[i])
    else:
    '''
    jointCount = countChain(startJoint) - countChain(endJoint)
    
    '''
    if(jointCount%2==0): #even joints
        middleJoint = int(jointCount/2) #-1
    else: #odd joints
        middleJoint = int(jointCount/2)
    '''

    # in order to find the middle joint, we need a list
    # of all of the joints between the start joint and the end joint
    # One way to do this is to get the long name of the end joint,
    # since we assume we're dealing with the same chain, the start
    # joint will be in the long name so we split the string by the short
    # name. This will give us a string that looks like this:
    # "joint2|joint3|joint4" We then split that again by "|" and now
    # have an array that looks like this: ["joint2", "joint3", "joint4"]
    # and we could now just find the halfway point within that array
    # and get our mid point.
    # As a warning, though, this method will break if the start, end or
    # middle joint don't have a unique name
    activeJoints = mc.ls(endJoint, l=True)[0].split(startJoint)[-1].split('|')

    middleJoint = activeJoints[int(floor(jointCount/2.0))]

    # at this point startJoint and endJoint are definitely going to be there.
    '''
    if not startJoint or not endJoint:
        ikControllerConstraints(ctl,handle[0],ctl2,joints[middleJoint])
    else:
    '''
    ikControllerConstraints(ctl,handle[0],ctl2,middleJoint)     

    #4. Try to apply controller to original selection
    mc.parent(ctlCst[0],name)
    mc.parent(ctl2,name)
    returns.append([ctlCst,ctlGrp,ctl,ctl2])

    return (name,returns)

#~~

def ikControllerConstraints(constraint, target, constraint2, target2):
    #3b. select parent of target joint

    # got rid of selection
    #mc.select(constraint, target)
    mc.parentConstraint(constraint, target, mo=1)
    #mc.select(constraint2, target2)
    snapToPos([constraint2, target2])
    #mc.select(constraint2,target)
    mc.poleVectorConstraint(constraint2, target)
    #mc.select(controller,handle)
    #cst1 = mc.parentConstraint(mo=1)
    #mc.select(constraint,handle)
    #cst2 = mc.poleVectorConstraint()

def countChain(target=None):
    if not target:
        try:
            target = s()
        except:
            print "Nothing selected or specified."
            return

    try:
        chain = py.listRelatives(target, ad=True)
        returnCount = len(chain)
    except:
        returnCount = 0
    print returnCount
    return(returnCount)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# IK Controller Alt Version (without David's improvements)
# Generally less reliable but can succeed when used as shelf button, where normal function breaks.

def ikCreateControllerAlt(startJoint=None, endJoint=None, controlType="cube", size=1.0, name="controller"):
    name = getUniqueName(name)
    #1. Store current selection
    if(startJoint):
        target = [startJoint]
    else:
        target = mc.ls(sl=True)

    finalGroup = mc.group(em=True, name=name)

    appendCtl = "_control"
    appendCst = "_constraint"
    appendGrp = "_group"
    appendPole = "_pole"

    returns = []

    for i in range(0,len(target)):
        joints = []
        #2. Create IK handle
        if not startJoint or not endJoint:
            mc.select(target[i])
            joints = mc.listRelatives(ad=True)
            joints.append(target[i])
            mc.select(joints[len(joints)-1],joints[0])
        else:
            mc.select(startJoint)
            joints = mc.listRelatives(ad=True)
            joints.append(startJoint)
            mc.select(startJoint,endJoint)

        handle = mc.ikHandle(solver="ikRPsolver")
        
        #3. Create controller
        ctl = controllerGeometry(controlType,size,name + str(i+1),appendCtl)
        ctl2 = controllerGeometry("sphere",size,name+appendPole + str(i+1),appendCtl)
        
        if not startJoint or not endJoint:
            mc.select(ctl,joints[0])
        else:
            mc.select(ctl,endJoint)

        snapToPos()
        #~~
        mc.select(ctl)
        mc.group(n=name + appendGrp + str(i+1))
        ctlGrp = mc.ls(sl=1)
        mc.group(n=name + appendCst + str(i+1))
        ctlCst = mc.ls(sl=1)
        #~~
        mc.parent(handle[0],ctlGrp[0])
        middleJoint = 0;
        if not startJoint or not endJoint:
            jointCount = countChainAlt(target[i])
        else:
            jointCount = countChainAlt(startJoint) - countChainAlt(endJoint)
        if(jointCount%2==0): #even joints
            middleJoint = int(jointCount/2) #-1
        else: #odd joints
            middleJoint = int(jointCount/2)
        
        if not startJoint or not endJoint:
            ikControllerConstraintsAlt(ctl,handle[0],ctl2,joints[middleJoint])      
        else:
            ikControllerConstraintsAlt(ctl,handle[0],ctl2,joints[middleJoint-countChainAlt(endJoint)])      

        #4. Try to apply controller to original selection
        mc.parent(ctlCst[0],name)
        mc.parent(ctl2,name)
        returns.append([ctlCst,ctlGrp,ctl,ctl2])

    return (name,returns)

#~~

def ikControllerConstraintsAlt(constraint, target, constraint2, target2):
    #3b. select parent of target joint
    mc.select(constraint, target)
    mc.parentConstraint(mo=1)
    mc.select(constraint2, target2)
    snapToPos()
    mc.select(constraint2,target)
    mc.poleVectorConstraint()
    #mc.select(controller,handle)
    #cst1 = mc.parentConstraint(mo=1)
    #mc.select(constraint,handle)
    #cst2 = mc.poleVectorConstraint()    

def countChainAlt(target=None):
    if not target:
        try:
            target = s()
        except:
            print "Nothing selected or specified."
            return

    try:
        chain = py.listRelatives(target, ad=True)
        returnCount = len(chain)
    except:
        returnCount = 0
    print returnCount
    return(returnCount)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Function to create an fk controller.
# Takes in controlType (string) that is either "circle", "sphere", or "cube"
# Takes in unit size
# creates the control curve and groups it and names the objects <name>_constraint, <name>_grp, <name>_control
# returns the names of the objects it's created  

def fkCreateController(targets=None, controlType="cube", size=1.0, name="controller"):
    name = getUniqueName(name)

    #1. Store current selection
    if not targets:
        targets = mc.ls(sl=1) # changed the name of this variable because we're expecting an array
    finalGroup = mc.group(em=True, name=name)

    appendCtl = "_control"
    appendCst = "_constraint"
    appendGrp = "_group"


    # shortened this a little and got rid of clamping the numReps to 1
    # it shouldn't run if there are no targets

    #numReps = len(target)
    #if(numReps<1):
    #    numReps=1
    
    # creating a return array
    returns = []

    for i in range( 0, len(targets) ):
        #2. Create controller

        # I'm appending the i to the controller name to create unique
        # names for the multiple fk controls. Otherwise it will try
        # to create something with the same name and fail.
        ctl = controllerGeometry(controlType,size,name+str(i+1),appendCtl)

        ctlGrp = mc.group(ctl, n=name + appendGrp + str(i+1)) # putting the grp right into a variable
        # also explicitly specifying what should be grouped, just in case we don't know
        # what's selected at that moment

        #ctlGrp = mc.ls(sl=1)
        
        ctlCst = mc.group(ctlGrp, n=name + appendCst + str(i+1)) # putting the grp right into a variable
        #ctlCst = mc.ls(sl=1)

        #3. Try to apply controller to original selection
        # let's get rid of the try, except so we know where the error is
        mc.parent(ctlCst,name) # ctlCst isn't an array since the grp command returns a string
        fkControllerConstraints(targets[i],ctlCst,ctl)

        returns.append([ctlCst,ctlGrp,ctl])

    return (name, returns)

#~~

def fkControllerConstraints(target,constraint,controller):
    #3a. snap controller to target joint location
    # was missing a .py here
    py.select(constraint,target)
    snapToPos()

    #3b. select parent of target joint
    mom = mc.listRelatives(target,parent=True)

    # changed this chunk of code so that it will apply the constraint to the fk controller
    # if there is a parent, but if not it will just continue on and apply the constraint
    # for the joint. Otherwise it will create the controller
    # but not do anything with it.
    if mom: #changed this to not look at mom's length, but just to check if mom has anything in it.
        # removed selection as you could apply constraint directly
        cst1 = mc.parentConstraint(mom[0],constraint, mo=1)
    else:
        print "No parent detected, not parentConstraining FK controller."

    # removed selection as you could apply constraint directly
    cst2 = mc.parentConstraint(controller,target, mo=0)    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    
def controllerGeometry(controlType="cube",size=1,name="controller",appendCtl="_ctl"):
    if(controlType=="circle"):
        ctl = mc.circle(r=size/2.0, n=name + appendCtl)
        #setAttr(ls(sl=1)[0] + ".rotateX",90)
    elif(controlType=="sphere"):
        ctl = mc.curve(n=name + appendCtl, d=1, p=((0*(size/2.0),1*(size/2.0),0*(size/2.0)),(0*(size/2.0),0.809017*(size/2.0),-0.587785*(size/2.0)),(0*(size/2.0),0.309017*(size/2.0),-0.951057*(size/2.0)),(0*(size/2.0),-0.309017*(size/2.0),-0.951057*(size/2.0)),(0*(size/2.0),-0.809017*(size/2.0),-0.587785*(size/2.0)),(0*(size/2.0),-1*(size/2.0),5.96046e-08*(size/2.0)),(0*(size/2.0),-0.809017*(size/2.0),0.587785*(size/2.0)),(0*(size/2.0),-0.309017*(size/2.0),0.951057*(size/2.0)),(0*(size/2.0),0.309017*(size/2.0),0.951057*(size/2.0)),(0*(size/2.0),0.809017*(size/2.0),0.587785*(size/2.0)),(0*(size/2.0),1*(size/2.0),0*(size/2.0)),(0.309017*(size/2.0),0.951057*(size/2.0),0*(size/2.0)),(0.809017*(size/2.0),0.587785*(size/2.0),0*(size/2.0)),(1*(size/2.0),0*(size/2.0),0*(size/2.0)),(0.809017*(size/2.0),-0.587785*(size/2.0),0*(size/2.0)),(0.309017*(size/2.0),-0.951057*(size/2.0),0*(size/2.0)),(0*(size/2.0),-1*(size/2.0),5.96046e-08*(size/2.0)),(-0.309017*(size/2.0),-0.951057*(size/2.0),0*(size/2.0)),(-0.809017*(size/2.0),-0.587785*(size/2.0),0*(size/2.0)),(-1*(size/2.0),-5.96046e-08*(size/2.0),0*(size/2.0)),(-0.809017*(size/2.0),0.587785*(size/2.0),0*(size/2.0)),(-0.309017*(size/2.0),0.951057*(size/2.0),0*(size/2.0)),(0*(size/2.0),1*(size/2.0),0*(size/2.0)),(-0.309017*(size/2.0),0.951057*(size/2.0),0*(size/2.0)),(-0.809017*(size/2.0),0.587785*(size/2.0),0*(size/2.0)),(-1*(size/2.0),-5.96046e-08*(size/2.0),0*(size/2.0)),(-0.809017*(size/2.0),0*(size/2.0),-0.587785*(size/2.0)),(-0.309017*(size/2.0),0*(size/2.0),-0.951057*(size/2.0)),(-0.309017*(size/2.0),0*(size/2.0),-0.951057*(size/2.0)),(-0.309017*(size/2.0),0*(size/2.0),-0.951057*(size/2.0)),(0.309017*(size/2.0),0*(size/2.0),-0.951057*(size/2.0)),(0.809017*(size/2.0),0*(size/2.0),-0.587785*(size/2.0)),(1*(size/2.0),0*(size/2.0),0*(size/2.0)),(0.809017*(size/2.0),0*(size/2.0),0.587785*(size/2.0)),(0.309017*(size/2.0),0*(size/2.0),0.951057*(size/2.0)),(-0.309017*(size/2.0),0*(size/2.0),0.951057*(size/2.0)),(-0.809017*(size/2.0),0*(size/2.0),0.587785*(size/2.0)),(-1*(size/2.0),-5.96046e-08*(size/2.0),0)), k=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37))
    elif(controlType=="star"):
        ctl = mc.curve(n=name + appendCtl, d=1, p=((-0.849836*(size/2.0),0*(size/2.0),-0.849836*(size/2.0)),(-0.79687*(size/2.0),0*(size/2.0),-0.330074*(size/2.0)),(-1.20185*(size/2.0),0*(size/2.0),0*(size/2.0)),(-0.79687*(size/2.0),0*(size/2.0),0.330074*(size/2.0)),(-0.849836*(size/2.0),0*(size/2.0),0.849836*(size/2.0)),(-0.330074*(size/2.0),0*(size/2.0),0.79687*(size/2.0)),(0*(size/2.0),0*(size/2.0),1.20185*(size/2.0)),(0.330074*(size/2.0),0*(size/2.0),0.79687*(size/2.0)),(0.849836*(size/2.0),0*(size/2.0),0.849836*(size/2.0)),(0.801233*(size/2.0),0*(size/2.0),0.326518*(size/2.0)),(1.20185*(size/2.0),0*(size/2.0),0*(size/2.0)),(0.801233*(size/2.0),0*(size/2.0),-0.326518*(size/2.0)),(0.849836*(size/2.0),0*(size/2.0),-0.849836*(size/2.0)),(0.326518*(size/2.0),0*(size/2.0),-0.801233*(size/2.0)),(0*(size/2.0),0*(size/2.0),-1.20185*(size/2.0)),(-0.333798*(size/2.0),0*(size/2.0),-0.801604*(size/2.0)),(-0.857352*(size/2.0),0*(size/2.0),-0.865126*(size/2.0))), k=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16))
    elif(controlType=="cube"):
        ctl = mc.curve(n=name + appendCtl, d=1, p=((-(size/2.0),(size/2.0),(size/2.0)),(-(size/2.0),-(size/2.0),(size/2.0)),((size/2.0),-(size/2.0),(size/2.0)),((size/2.0),(size/2.0),(size/2.0)),(-(size/2.0),(size/2.0),(size/2.0)),(-(size/2.0),(size/2.0),-(size/2.0)),((size/2.0),(size/2.0),-(size/2.0)),((size/2.0),(size/2.0),(size/2.0)),((size/2.0),-(size/2.0),(size/2.0)),((size/2.0),-(size/2.0),-(size/2.0)),((size/2.0),(size/2.0),-(size/2.0)),((size/2.0),(size/2.0),(size/2.0)),((size/2.0),-(size/2.0),(size/2.0)),(-(size/2.0),-(size/2.0),(size/2.0)),(-(size/2.0),-(size/2.0),-(size/2.0)),((size/2.0),-(size/2.0),-(size/2.0)),(-(size/2.0),-(size/2.0),-(size/2.0)),(-(size/2.0),(size/2.0),-(size/2.0)),(-(size/2.0),(size/2.0),(size/2.0)),(-(size/2.0),-(size/2.0),(size/2.0))), k=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19))
    else:
        print 'Nothing created; valid types are "circle", "sphere", "star", and "cube".'
        return
    return ctl    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def snapToPos(s=None):
    if not s:
        s = mc.ls(sl=1)
    for i in range(0,len(s)-1):
        cst0 = mc.parentConstraint(s[len(s)-1],s[i],mo=0)
        mc.delete(cst0)    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def addAttrVector(target=None, name="tempVector"):
    if not target:
        target = mc.ls(sl=1)
    for i in range(0,len(target)):
        mel.eval("addAttr -ln \"" + name + "\"  -at double3  "+target[i]+";")
        mel.eval("addAttr -ln \""+name+"X\"  -at double -p "+name+"  "+target[i]+";")
        mel.eval("addAttr -ln \""+name+"Y\"  -at double -p "+name+"  "+target[i]+";")
        mel.eval("addAttr -ln \""+name+"Z\"  -at double -p "+name+"  "+target[i]+";")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + ";")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + "X;")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + "Y;")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + "Z;")

def addAttrFloat(target=None, name="tempFloat"):
    if not target:
        target = mc.ls(sl=1)
    for i in range(0,len(target)):
        mel.eval("addAttr -ln \"" + name + "\"  -at double  "+target[i]+";")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + ";")

def addAttrFloatSlider(target=None, name="tempFloat",minVal=0,maxVal=1,defaultVal=0):
    if not target:
        target = mc.ls(sl=1)
    for i in range(0,len(target)):
        mel.eval("addAttr -ln \"" + name + "\"  -at double  -min "+str(minVal)+" -max "+str(maxVal)+" -dv "+str(defaultVal)+"  "+target[i]+";")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + ";")

def addAttrString(target=None, name="tempString"):
    if not target:
        target = mc.ls(sl=1)
    for i in range(0,len(target)):
        mel.eval("addAttr -ln \"" + name + "\"  -dt \"string\"  "+target[i]+";")
        #mel.eval("setAttr -e-keyable true "+target[i]+"." + name + ";")

def addAttrBoolean(target=None, name="tempBoolean"):
    returns = []
    if not target:
        target = mc.ls(sl=1)
    for i in range(0,len(target)):
        mel.eval("addAttr -ln \"" + name + "\"  -at bool  "+target[i]+";")
        mel.eval("setAttr -e-keyable true "+target[i]+"." + name + ";")
        val = target[i] + "." + name
        returns.append(val)
    return returns

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

fk=fkCreateController
ik=ikCreateController
fkik = fkikCreateController