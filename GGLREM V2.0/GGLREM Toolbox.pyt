#-------------------------------------------------------------------------------
# Created:     02/06/2018
# ArcGIS version: 10.5.1
# Python version: 2.7
# GGLREM version: 2.0.0
# First release: 08/20/2018
#Latest release: 11/09/2019

# Name:        GGL REM Toolbox
# Purpose: Series of tools to build a Relative Elevation Model (REM)
# based on the Geomorphic Grade Line (GGL).
# Author:      Matt Helstab
#
# Copyright:   (c) jmhelstab 2018
# Licence:     GNU General Public License v3.0
#-------------------------------------------------------------------------------

#Import Modules
import arcpy
import os
import sys
from arcpy.sa import *
import numpy



#Define Toolboxs
class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "GGL REM Toolbox"
        self.alias = "GGLREM"

        # List of tool classes associated with this toolbox
        self.tools = [CrossSections, Centerline, CenterlineStations, REM, Polygons, Update]

#Create Centerline Feature Class Tool Parameters
class Centerline(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "1. Create a Centerline Feature Class"
        self.description = "Create a polyline Feature Class in the current workspace with expected Fields and Data Types for the Create Cross Section Tool"
        self.canRunInBackground = False

    def getParameterInfo(self):
        workspaceLOC = arcpy.Parameter(
            displayName = "Input Workspace Location",
            name = "WorkspaceLocation",
            datatype = "DEWorkspace",
            parameterType = "Required",
            direction = "Input")
        workspaceLOC.filter.list = ["File System"]

        geodatabaseLOC = arcpy.Parameter(
            displayName = "Input Project Geodatabase",
            name = "geoLocation",
            datatype = "DEWorkspace",
            parameterType = "Required",
            direction = "Input")
        geodatabaseLOC.filter.list = ["Local Database", "Remote Database"]

        centerCOORD = arcpy.Parameter(
            displayName = "Match Coordinate System to LiDAR DEM",
            name = "CoordinateSystem",
            datatype = "GPSpatialReference",
            parameterType = "Required",
            direction = "Input")

        nameFC = arcpy.Parameter(
            displayName = "Input Centerline Feature Class Name",
            name = "CenterlineName",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Output")

        params = [workspaceLOC, geodatabaseLOC, centerCOORD, nameFC]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        #Set Local Variables
        ws = parameters[0].valueAsText
        gdb = parameters[1].valueAsText
        dem = parameters[2].valueAsText
        name_fc = parameters[3].valueAsText
        cl_name = "Centerline_" + name_fc

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        #Create Feature Class
        arcpy.AddMessage("Creating Feature Class")
        arcpy.CreateFeatureclass_management(gdb, cl_name, "POLYLINE", "", "", "", dem)

        #Add Route ID Field to Feature Class
        arcpy.AddMessage("Adding Route ID Field")
        arcpy.AddField_management(cl_name, "ROUTEID", "TEXT")

        #Add Layers
        arcpy.AddMessage("Adding Centerline Layer")
        Layer_cl_name = arcpy.mapping.Layer(cl_name)
        arcpy.mapping.AddLayer(df, Layer_cl_name)

        return

#Create Cross Section Tool Parameters
class CrossSections(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "2. Create Cross Sections and Routed Centerline"
        self.description = "Creates cross section polylines and routed valley centerline."
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter [0]
        inFC = arcpy.Parameter(
            displayName = "Input Centerline Feature Class",
            name = "InputCenterline",
            datatype = ["GPFeatureLayer", "DEFeatureClass", "DEShapefile"],
            parameterType = "Required",
            direction = "Input")

        #Third parameter [1]
        routeID = arcpy.Parameter(
            displayName = "Select Centerline Route ID",
            name = "RouteID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        routeID.filter.type = "ValueList"
        routeID.filter.list = []

        #Forth parameter [2]
        offCenter = arcpy.Parameter(
            displayName = "Input Offset Distance From Centerline",
            name = "OffsetLeft",
            datatype = "GPLong",
            parameterType = "Required",
            direction = "Input")

        #Sixth parameter [3]
        drawDirection = arcpy.Parameter(
            displayName = "Select Direction to Start Stationing From",
            name = "DrawDirection",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        drawDirection.filter.type = "ValueList"
        drawDirection.filter.list = ["UPPER_LEFT", "UPPER_RIGHT", "LOWER_LEFT", "LOWER_RIGHT"]

        params = [inFC, routeID, offCenter, drawDirection]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[0].value:
            with arcpy.da.SearchCursor(parameters[0].valueAsText, 'ROUTEID') as rows:
                parameters[1].filter.list = sorted(list(set([row[0] for row in rows])))
        else:
            parameters[1].filter.list = []
        return

    def updateMessages(self, parameters):
        if parameters[2].altered:
            if parameters[2].value <= 0:
                parameters[2].setErrorMessage('''Offset Value must be greater than zero.''')

        return

    def execute(self, parameters, messages):

        #Get Parameter Inputs
        fc_in = parameters[0].valueAsText
        route_id = parameters[1].valueAsText
        route_field = "ROUTEID"
        o_left = parameters[2].valueAsText
        o_right = parameters[2].valueAsText
        draw_dir = parameters[3].valueAsText
        length_id = "LOCATION"
        fc_routed = "Routed_" + route_id
        off_table = "Offset_Table_" + route_id
        merged = "Merged_" + route_id
        x_sec = "CrossSections_" + route_id
        desc = arcpy.Describe(fc_in)
        gdb = desc.path

        #Set Workspace Environment and Map Properties
        from arcpy import env
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        # Process: Create Routes
        arcpy.AddMessage("Creating Routes")
        arcpy.CreateRoutes_lr(fc_in, route_field, fc_routed, "LENGTH", "", "", draw_dir, "", "", "IGNORE", "INDEX")

        #Create Table
        arcpy.AddMessage("Building Offset Table")
        arcpy.CreateTable_management(gdb, off_table)

        #Add Fields
        arcpy.AddField_management(off_table, "LOCATION", "LONG")
        arcpy.AddField_management(off_table, "OFFSET_LEFT", "LONG")
        arcpy.AddField_management(off_table, "OFFSET_RIGHT", "LONG")
        arcpy.AddField_management(off_table, route_field, "TEXT")


        #Extract values from Centerline Polyline and create variable with desired row length
        arcpy.AddMessage("Extracting Values")
        fields_centerline = ['shape_length', 'shape_Length', 'shape_LENGTH', 'Shape_length', 'Shape_Length', 'Shape_LENGTH', 'SHAPE_length', 'SHAPE_Length', 'SHAPE_LENGTH',]
        LOCATION1 = arcpy.da.SearchCursor(fc_routed, fields_centerline,).next()[0]
        LENGTH = int(LOCATION1)
        LOCATION2 = range(1,LENGTH)

        NAME =  arcpy.da.SearchCursor(fc_in, route_field,)
        NAME = [NAME] * LENGTH

        #Append Extracted Values to Offset_Table
        arcpy.AddMessage("Populating Offset Table")
        fields = ["LOCATION", "OFFSET_LEFT", "OFFSET_RIGHT", route_field]
        cursor = arcpy.da.InsertCursor(off_table, fields)
        for x in xrange(1, LENGTH):
            cursor.insertRow((x, o_left, o_right, route_id, ))
        del(cursor)

        #Process: Make Route Event Layers Left and Right
        arcpy.AddMessage("Creating Offset Stations")
        arcpy.MakeRouteEventLayer_lr(fc_routed,"ROUTEID",off_table,"ROUTEID POINT LOCATION", "leftoff", "OFFSET_LEFT","NO_ERROR_FIELD","NO_ANGLE_FIELD","NORMAL","ANGLE","LEFT","POINT")
        arcpy.MakeRouteEventLayer_lr(fc_routed,"ROUTEID",off_table,"ROUTEID POINT LOCATION", "rightoff", "OFFSET_RIGHT","NO_ERROR_FIELD","NO_ANGLE_FIELD","NORMAL","ANGLE","RIGHT","POINT")

        #Merg#Merge Offset Event Layers

        #arcpy.Merge_management(["leftoff","rightoff"], (os.path.join(sw, merged)), "")
        arcpy.AddMessage("Merging Offsets")
        arcpy.Merge_management(["leftoff","rightoff"], merged, "")

        #Convert Points to Lines
        arcpy.AddMessage("Converting Offset Points to Cross Sections")
        arcpy.PointsToLine_management(merged, x_sec, "LOCATION", "LOCATION")

        #Add Layers
        Layer_fc_routed = arcpy.mapping.Layer(fc_routed)
        arcpy.mapping.AddLayer(df, Layer_fc_routed)

        Layer_x_sec = arcpy.mapping.Layer(x_sec)
        arcpy.mapping.AddLayer(df, Layer_x_sec)

        #Delete Temporary Features
        arcpy.Delete_management("merged")
        arcpy.Delete_management("leftoff")
        arcpy.Delete_management("rightoff")
        return

# Create Centerline Stations Tool Parameters
class CenterlineStations(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "3. Create GGL Table and Centerline Stations"
        self.description = "Creates a Point Feature Class at each intersection of the Centerline and Cross Section polylines, and then appends elevation data to each point."
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter
        inFC1 = arcpy.Parameter(
            displayName = "Input Routed Centerline Feature Class",
            name = "InputCenterlineRouted",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")

        #Second parameter
        routeID = arcpy.Parameter(
            displayName = "Select Centerline Route ID",
            name = "RouteID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        routeID.filter.type = "ValueList"
        routeID.filter.list = []

        #Third parameter
        inFC2 = arcpy.Parameter(
            displayName = "Input Cross Section Feature Class",
            name = "InputCrossSection",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")

        bufferBOOLEAN = arcpy.Parameter(
            displayName = "Include Centerline Buffer Distance?",
            name = "bufferBoolean",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        bufferBOOLEAN.filter.type = "ValueList"
        bufferBOOLEAN.filter.list = ["Yes", "No"]

        #Fourth parameter
        buffer = arcpy.Parameter(
            displayName = "Input Centerline Buffer Distance",
            name = "buffer",
            datatype = "GPLong",
            parameterType = "Optional",
            direction = "Input")
        buffer.value = "1"

        #Fifth parameter
        inRASTER = arcpy.Parameter(
            displayName = "Input LiDAR Digital Elevation Model",
            name = "InputLidar",
            datatype = ["GPRasterLayer", "GPLayer", "DEMosaicDataset", "GPMosaicLayer", "DERasterDataset", "GPRasterDataLayer"],
            parameterType = "Required",
            direction = "Input")

        params = [inFC1, routeID, inFC2, bufferBOOLEAN, buffer, inRASTER]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        if parameters[0].value:
            with arcpy.da.SearchCursor(parameters[0].valueAsText, "ROUTEID") as rows:
                parameters[1].filter.list = [row[0] for row in rows]
        else:
            parameters[1].filter.list = []

        if parameters[3].value == "Yes":
            parameters[4].enabled = True
            parameters[4].parameterType = "Required"
        else:
            parameters[4].enabled = False
            parameters[4].parameterType = "Disabled"
            parameters[4].value = "1"



        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if parameters[4].altered:
            if parameters[4].value <= 0:
                parameters[4].setErrorMessage('''Buffer Value must be an integer greater than zero.''')
        return

    def execute(self, parameters, messages):

        #Set Local Variables
        centerroute = parameters[0].valueAsText
        routeid = parameters[1].valueAsText
        crosssection = parameters[2].valueAsText
        bufferboolean = parameters[3].valueAsText
        buffer = parameters[4].valueAsText
        raster = parameters[5].valueAsText
        table_name = "GGL_Table_" + routeid
        buf_table_name = "GGLBUF_Table_" + routeid
        stations = "Stations_" + routeid
        clip_crosssection = crosssection + "_clipped"
        inFeatures = [centerroute, crosssection]
        desc = arcpy.Describe(centerroute)
        gdb = desc.path
        out_table = gdb + "/" + "GGL_Table_" + routeid
        out_table_buf = gdb + "/" + "GGLBUF_Table_" + routeid
        dir = os.path.dirname(gdb)
        csv = table_name + ".csv"
        csv_buff = buf_table_name + ".csv"

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        if "No" in bufferboolean:
            arcpy.AddMessage("No Offeset Buffer")
            arcpy.AddMessage("Intersecting Centerline and Cross Section Polylines...")
            arcpy.Intersect_analysis(inFeatures, "xsec", "", "", "POINT")

            arcpy.MultipartToSinglepart_management("xsec", "xsec2")

            #Extract elevation data from DEM to Centerline Station Points
            arcpy.AddMessage("Extracting Elevation Values...")
            arcpy.sa.ExtractValuesToPoints("xsec2", raster, stations, "INTERPOLATE")
            arcpy.Delete_management("xsec")
            arcpy.Delete_management("xsec2")

            #Add Layers
            arcpy.AddMessage("Adding Stations to TOC...")
            Layer_stations = arcpy.mapping.Layer(stations)
            arcpy.mapping.AddLayer(df, Layer_stations)

            #Centerline Model Building
            ##Extract Values to evalue centelline slope
            arcpy.AddMessage("Building GGL...")
            px = [row[0] for row in arcpy.da.SearchCursor(stations, "LOCATION")]
            py = [row[0] for row in arcpy.da.SearchCursor(stations, "RASTERVALU")]

            p_2 = numpy.power(px, 2)
            p_3 = numpy.power(px, 3)
            p_4 = numpy.power(px, 4)
            p_5 = numpy.power(px, 5)

            #Linear Model
            arcpy.AddMessage("LINEAR")
            polyfit_1 = numpy.polyfit(px, py, 1)
            p1 = numpy.polyval(polyfit_1, px)

            #Second Order
            arcpy.AddMessage("QUADRATIC")
            polyfit_2 = numpy.polyfit(px, py, 2)
            p2 = numpy.polyval(polyfit_2, px)

            #Third Order
            arcpy.AddMessage("THIRD ORDER POLY")
            polyfit_3 = numpy.polyfit(px, py, 3)
            p3 = numpy.polyval(polyfit_3, px)

            #Fourth Order
            arcpy.AddMessage("FOURTH ORDER POLY")
            polyfit_4= numpy.polyfit(px, py, 4)
            p4 = numpy.polyval(polyfit_4, px)

            #Fifth Order
            arcpy.AddMessage("FIFTH ORDER POLY")
            polyfit_5= numpy.polyfit(px, py, 5)
            p5 = numpy.polyval(polyfit_5, px)

            #Build Structured Array
            ##Set Data Types
            arcpy.AddMessage("Almost Done...")
            dt = {'names':['LOCATION','LIDAR', 'LINEAR', 'POLY2', 'POLY3', 'POLY4', 'POLY5'], 'formats':[numpy.int, numpy.float32, numpy.float32, numpy.float32, numpy.float32, numpy.float32, numpy.float32]}

            ##Build Blank Structured Array
            poly = numpy.zeros(len(px), dtype=dt)

            ##Add values to Structured Array
            poly['LOCATION'] = px
            poly['LIDAR'] = py
            poly['LINEAR'] = p1
            poly['POLY2'] = p2
            poly['POLY3'] = p3
            poly['POLY4'] = p4
            poly['POLY5'] = p5

            #Convert Structured Array to Table
            arcpy.da.NumPyArrayToTable(poly, out_table)

            #Create a .cvs table for model evaluation in R Studio
            fm_fields = ["LOCATION", "LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"]
            arcpy.TableToTable_conversion(out_table, dir, csv)

            #Join Model Output to Cross Sections and Centerline Stations Feature Classes
            arcpy.AddMessage("Joining Modeled Values to Features")
            arcpy.JoinField_management(stations, "LOCATION", out_table, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"])
            arcpy.JoinField_management(crosssection, "LOCATION", out_table, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"])

        else:
            #Creating Centerling Stations Point Feature Class
            arcpy.AddMessage("Offeset Buffer Entered")
            arcpy.AddMessage("Intersecting Centerline and Cross Section Polylines...")
            arcpy.Intersect_analysis(inFeatures, "xsec", "", "", "POINT")

            arcpy.MultipartToSinglepart_management("xsec", "xsec2")

            #Extract elevation data from DEM to Centerline Station Points
            arcpy.AddMessage("Extracting Elevation Values...")
            arcpy.sa.ExtractValuesToPoints("xsec2", raster, stations, "INTERPOLATE")

            #Buffer Centerline
            arcpy.AddMessage("Evaluting Buffer Distance...")
            arcpy.Buffer_analysis(centerroute, "center_buff", buffer, "FULL", "FLAT", "ALL", "", "")

            #Clip Cross Sections to Centerline Buffer
            arcpy.AddMessage("Clipping Buffer Distance...")
            arcpy.Clip_analysis(crosssection, "center_buff", clip_crosssection, "")

            #Convert Clipped Cross Sections to Raster
            arcpy.AddMessage("Converting things...")
            arcpy.PolylineToRaster_conversion(clip_crosssection, "LOCATION", "clip_xsec_raster", "", "LOCATION", "1")

            #Convert Clipped Cross SEction Raster to Points
            arcpy.RasterToPoint_conversion("clip_xsec_raster", "xsec_clipped_points", "VALUE")

            #Extract elevation data from DEM to Clipped Cross Section Station Points
            arcpy.sa.ExtractValuesToPoints("xsec_clipped_points", raster, "xsec_stations", "INTERPOLATE")

            #Delete Unneeded Feature Classes
            arcpy.Delete_management("xsec")
            arcpy.Delete_management("xsec2")
            arcpy.Delete_management("center_buff")
            arcpy.Delete_management("clip_xsec_raster")
            arcpy.Delete_management("xsec_clipped_points")

            #Add Layers
            Layer_stations = arcpy.mapping.Layer(stations)
            arcpy.mapping.AddLayer(df, Layer_stations)

            #Centerline Model Building
            ##Extract Values to evalue centelline slope
            arcpy.AddMessage("Building GGL...")
            px = [row[0] for row in arcpy.da.SearchCursor("xsec_stations", "grid_code")]
            py = [row[0] for row in arcpy.da.SearchCursor("xsec_stations", "RASTERVALU")]

            p_2 = numpy.power(px, 2)
            p_3 = numpy.power(px, 3)
            p_4 = numpy.power(px, 4)
            p_5 = numpy.power(px, 5)

            #Linear Model
            arcpy.AddMessage("LINEAR")
            polyfit_1 = numpy.polyfit(px, py, 1)
            p1 = numpy.polyval(polyfit_1, px)

            #Second Order
            arcpy.AddMessage("QUADRATIC")
            polyfit_2 = numpy.polyfit(px, py, 2)
            p2 = numpy.polyval(polyfit_2, px)

            #Third Order
            arcpy.AddMessage("THIRD ORDER POLY")
            polyfit_3 = numpy.polyfit(px, py, 3)
            p3 = numpy.polyval(polyfit_3, px)

            #Fourth Order
            arcpy.AddMessage("FOURTH ORDER POLY")
            polyfit_4= numpy.polyfit(px, py, 4)
            p4 = numpy.polyval(polyfit_4, px)

            #Fifth Order
            arcpy.AddMessage("FIFTH ORDER POLY")
            polyfit_5= numpy.polyfit(px, py, 5)
            p5 = numpy.polyval(polyfit_5, px)

            #Build Structured Array
            ##Set Data Types
            arcpy.AddMessage("Almost Done...")
            dt = {'names':['LOCATION','LIDAR', 'LINEAR', 'POLY2', 'POLY3', 'POLY4', 'POLY5'], 'formats':[numpy.int, numpy.float32, numpy.float32, numpy.float32, numpy.float32, numpy.float32, numpy.float32]}

            ##Build Blank Structured Array
            poly = numpy.zeros(len(px), dtype=dt)

            ##Add values to Structured Array
            poly['LOCATION'] = px
            poly['LIDAR'] = py
            poly['LINEAR'] = p1
            poly['POLY2'] = p2
            poly['POLY3'] = p3
            poly['POLY4'] = p4
            poly['POLY5'] = p5

            #Convert Structured Array to Table
            arcpy.da.NumPyArrayToTable(poly, out_table_buf)

            #Create a .cvs table for model evaluation in R Studio
            fm_fields = ["LOCATION", "LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"]
            arcpy.TableToTable_conversion(out_table_buf, dir, csv_buff)

            #Join Model Output to Cross Sections and Centerline Stations Feature Classes
            arcpy.AddMessage("Joining Modeled Values to Features")
            arcpy.JoinField_management(stations, "LOCATION", out_table_buf, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"])
            arcpy.JoinField_management(crosssection, "LOCATION", out_table_buf, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4", "POLY5"])

            #Delete Unneeded Feature Classes
            arcpy.Delete_management("xsec_stations")
        return

class REM(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "4. Create Relative Elevation Model(s)"
        self.description = "Joins modeled GGL elevations to cross sections, converts cross sections to a raster, and lastly subtracts cross section raster from LiDAR raster to produce the REM."
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter
        inNAME = arcpy.Parameter(
            displayName = "Input Unique GGLREM Name",
            name = "GGLREMname",
            datatype = ["GPString"],
            parameterType = "Required",
            direction = "Input")

        #Second parameter
        inFC = arcpy.Parameter(
            displayName = "Input Cross Section Feature Class",
            name = "InputCrossSections",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")

        #Third parameter
        gglLIST = arcpy.Parameter(
            displayName = "Select Values/Model to Construct Relative Eleavtion Model",
            name = "GglList",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input",
            multiValue = "True")
        gglLIST.filter.type = "ValueList"
        gglLIST.filter.list = ["Custom", "Linear Model", "Polynomial 2nd", "Polynomial 3rd", "Polynomial 4th", "Polynomial 5th"]

        #Fourth parameter
        gglCUST = arcpy.Parameter(
            displayName = "Input Custom GGL Table [ONLY IF RUNNING CUSTOM MODEL]",
            name = "CustomGglTable",
            datatype = "DETable",
            parameterType = "Optional",
            direction = "Input")

        #Fifth parameter
        gglFIELD = arcpy.Parameter(
            displayName = "Select Field with GGL Values for Detrending",
            name = "CustomGglField",
            datatype = "Field",
            parameterType = "Optional",
            direction = "Input")
        gglFIELD.filter.list =[]
        gglFIELD.parameterDependencies = [gglCUST.name]

        #Sixth parameter
        inDEM = arcpy.Parameter(
            displayName = "Input LiDAR DEM",
            name = "InputLidar",
            datatype = ["GPRasterLayer","DERasterDataset", "DERasterCatalog"],
            parameterType = "Required",
            direction = "Input")

        #Seventh parameter
        outREM = arcpy.Parameter(
            displayName = "Output Relative Elevation Model(s)",
            name = "OutputREM",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input",
            multiValue = "True")
        outREM.filter.type = "ValueList"
        outREM.filter.list = ["Integer_Meters", "Integer_Decimeters", "Integer_Feet", "Float_Feet"]

        params = [inNAME, inFC, gglLIST, gglCUST, gglFIELD, inDEM, outREM]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        if parameters[3].value:
            parameters[4].enabled = True
        else:
            parameters[4].enabled = False
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        #Set local variables
        gglrem_name = parameters[0].valueAsText
        crosssections = parameters[1].valueAsText
        detrend = parameters[2].valueAsText
        ggl_table = parameters[3].valueAsText
        ggl_field = parameters[4].valueAsText
        lidar = parameters[5].valueAsText
        rems = parameters[6].valueAsText
        desc = arcpy.Describe(crosssections)
        gdb = desc.path

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        #REM in Float Meters
        if "Custom" in detrend:
                arcpy.AddMessage("Building Cutom GGLREM")
                arcpy.CopyRows_management(ggl_table, "ggl_table_custom")
                arcpy.JoinField_management(crosssections, "LOCATION", "ggl_table_custom", "LOCATION", ggl_field)
                arcpy.PolylineToRaster_conversion(crosssections, ggl_field, "Custom", "", "", "1")
                arcpy.Minus_3d(lidar, "Custom", gglrem_name + "_Detrended_Custom_Float_m")
                Layer_CUSTOM_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Custom_Float_m")
                arcpy.mapping.AddLayer(df, Layer_CUSTOM_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Custom_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Custom_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Custom_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Custom_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Custom_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Custom_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Custom_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Custom_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Custom_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Custom_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Custom_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Custom_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        if "Linear Model" in detrend:
                arcpy.AddMessage("Building Linear GGLREM")
                arcpy.PolylineToRaster_conversion(crosssections, "LINEAR", "Linear", "", "", "1")
                arcpy.Minus_3d(lidar, "Linear", gglrem_name + "_Detrended_Linear_Float_m")
                Layer_LINEAR_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Linear_Float_m")
                arcpy.mapping.AddLayer(df, Layer_LINEAR_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Linear_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Linear_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Linear_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Linear_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Linear_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Linear_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Linear_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Linear_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Linear_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Linear_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Linear_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Linear_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        if "Polynomial 2nd" in detrend:
                arcpy.AddMessage("Building Quadratic GGLREM")
                arcpy.PolylineToRaster_conversion(crosssections, "POLY2", "Poly2", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly2", gglrem_name + "_Detrended_Poly2_Float_m")
                Layer_POLY2_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly2_Float_m")
                arcpy.mapping.AddLayer(df, Layer_POLY2_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Poly2_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Poly2_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly2_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Poly2_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Poly2_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly2_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Poly2_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Poly2_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly2_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Poly2_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Poly2_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly2_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        if "Polynomial 3rd" in detrend:
                arcpy.AddMessage("Building 3rd Order Poly GGLREM")
                arcpy.PolylineToRaster_conversion(crosssections, "POLY3", "Poly3", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly3", gglrem_name + "_Detrended_Poly3_Float_m")
                Layer_POLY3_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly3_Float_m")
                arcpy.mapping.AddLayer(df, Layer_POLY3_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Poly3_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Poly3_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly3_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Poly3_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Poly3_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly3_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Poly3_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Poly3_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly3_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Poly3_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Poly3_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly3_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        if "Polynomial 4th" in detrend:
                arcpy.AddMessage("Building 4th Order Poly GGLREM")
                arcpy.PolylineToRaster_conversion(crosssections, "POLY4", "Poly4", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly4", gglrem_name + "_Detrended_Poly4_Float_m")
                Layer_POLY4_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly4_Float_m")
                arcpy.mapping.AddLayer(df, Layer_POLY4_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Poly4_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Poly4_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly4_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Poly4_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Poly4_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly4_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Poly4_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Poly4_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly4_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Poly4_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Poly4_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly4_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        if "Polynomial 5th" in detrend:
                arcpy.AddMessage("Building 5th Order Poly GGLREM")
                arcpy.PolylineToRaster_conversion(crosssections, "POLY5", "Poly5", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly5", gglrem_name + "_Detrended_Poly5_Float_m")
                Layer_POLY5_Float_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly5_Float_m")
                arcpy.mapping.AddLayer(df, Layer_POLY5_Float_M)
                if "Integer_Meters" in rems:
                    int_m = Int(Raster(gglrem_name + "_Detrended_Poly5_Float_m"))
                    int_m.save(gglrem_name + "_Detrended_Poly5_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly5_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster(gglrem_name + "_Detrended_Poly5_Float_m") * 10 ))
                    deci_m.save(gglrem_name + "_Detrended_Poly5_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly5_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster(gglrem_name + "_Detrended_Poly5_Float_m") * 3.28084)
                    int_ft.save(gglrem_name + "_Detrended_Poly5_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly5_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
                if "Float_Feet" in rems:
                    flt_ft = Raster(gglrem_name + "_Detrended_Poly5_Float_m") * 3.28084
                    flt_ft.save(gglrem_name + "_Detrended_Poly5_Flt_Ft")
                    Layer_GGLREM_Flt_Ft = arcpy.mapping.Layer(gglrem_name + "_Detrended_Poly5_Flt_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Flt_Ft)

        #Delete Unneeded Feature Classes
        arcpy.Delete_management("Lidar")
        arcpy.Delete_management("Linear")
        arcpy.Delete_management("Poly2")
        arcpy.Delete_management("Poly3")
        arcpy.Delete_management("Poly4")
        arcpy.Delete_management("Poly5")

        arcpy.AddMessage("KEEP ASKING QUESTIONS!")

        return
class Polygons(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "5. Create Cut/Fill Polygon Feature Class"
        self.description = "Create a polygon for evaluating CUT and FILL."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        nameFC = arcpy.Parameter(
            displayName = "Input Cut/Fill Feature Class Name",
            name = "CenterlineName",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Output")

        geodatabaseLOC = arcpy.Parameter(
            displayName = "Input Project Geodatabase",
            name = "geoLocation",
            datatype = "DEWorkspace",
            parameterType = "Required",
            direction = "Input")
        geodatabaseLOC.filter.list = ["Local Database", "Remote Database"]

        cordFC = arcpy.Parameter(
            displayName = "Match Coordinate System to LiDAR DEM",
            name = "CoordinateSystem",
            datatype = "GPSpatialReference",
            parameterType = "Required",
            direction = "Input")

        params = [nameFC, geodatabaseLOC, cordFC]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        name_fc = parameters[0].valueAsText
        gdb = parameters[1].valueAsText
        dem = parameters[2].valueAsText
        poly_name = "Cut_Fill_" + name_fc

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]


        #Create Feature Class
        arcpy.AddMessage("Creating Feature Class")
        arcpy.CreateFeatureclass_management(gdb, poly_name, "POLYGON", "", "", "", dem)

        #Add Field to Feature Class
        arcpy.AddMessage("Adding Descriptive Fields to Feature Class")
        arcpy.AddField_management(poly_name, "TYPE", "TEXT")
        arcpy.AddField_management(poly_name, "ZONE", "TEXT")
        arcpy.AddField_management(poly_name, "ID", "TEXT")
        arcpy.AddField_management(poly_name, "GROUP", "TEXT")
        arcpy.AddField_management(poly_name, "DESCRIPTION", "TEXT")

        #Add Layers
        arcpy.AddMessage("Adding Redistribution Layer")
        Layer_poly_name = arcpy.mapping.Layer(poly_name)
        arcpy.mapping.AddLayer(df, Layer_poly_name)
        return


class Update(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "6. Calculate Cut and Fill Volumes"
        self.description = "Applies Target REM Zonal Statistics to each Cut/Fill polygon."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        inFC = arcpy.Parameter(
            displayName = "Input Cut/Fill Feature Class",
            name = "RedistroName",
            datatype = ["GPFeatureLayer", "DEFeatureClass", "DEShapefile"],
            parameterType = "Required",
            direction = "Input")

        zoneID = arcpy.Parameter(
            displayName = "Select Unique Zone ID Field",
            name = "RouteID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        zoneID.filter.type = "ValueList"
        zoneID.filter.list = []

        inRASTER = arcpy.Parameter(
            displayName = "Input Relative Elevation Model (_Float_m)",
            name = "REM",
            datatype = ["GPRasterLayer", "GPLayer", "DEMosaicDataset", "GPMosaicLayer", "DERasterDataset", "GPRasterDataLayer"],
            parameterType = "Required",
            direction = "Input")

        inTARGET = arcpy.Parameter(
            displayName = "Input Target Elevation (m)",
            name = "TargetElevation",
            datatype = "GPDouble",
            parameterType = "Required",
            direction = "Input")

        params = [inFC, zoneID, inRASTER, inTARGET]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        if parameters[0].value:
            fieldnames = [f.name for f in arcpy.ListFields(parameters[0].valueAsText)]
            parameters[1].filter.list = fieldnames
        else:
            parameters[1].filter.list = []
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        zone_poly = parameters[0].valueAsText
        zone_field = parameters[1].valueAsText
        ggl_raster = parameters[2].valueAsText
        target_re = parameters[3].valueAsText
        target_np = numpy.array(target_re, dtype=numpy.float32)
        target = target_np * -1
        out_table = "Volumes_" + zone_poly
        desc = arcpy.Describe(zone_poly)
        arcpy.AddMessage(desc)
        gdb = desc.path
        arcpy.AddMessage(gdb)
        dir = os.path.dirname(gdb)
        arcpy.AddMessage(dir)
        csv = out_table + ".csv"
        output_raster = gdb + "/"+ ggl_raster + "_ADJUSTED"

        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = True
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        arcpy.AddMessage(df)

        arcpy.AddMessage("Gathering Relative Elevations...")
        #"Clip" the GGLREM to the Zone Polys
        zone_mask = ExtractByMask (ggl_raster, zone_poly)
        #Adject the clipped GGLREM ta target relative elevation
        adj_ggl = zone_mask + target
        #adj_raster = arcpy.gp.Plus_sa(in_value_raster, t2, output_raster)
        #adj_raster.save(in_value_raster + "_ADJUSTED")

        #ZonalStatisticsAsTable (in_zone_data, zone_field, in_value_raster, out_table, {ignore_nodata}, {statistics_type})
        arcpy.AddMessage("Applying Zonal Stats...")
        arcpy.sa.ZonalStatisticsAsTable(zone_poly, zone_field, adj_ggl, out_table, 'DATA' , 'ALL')
        arcpy.AddMessage("Appending Feature...")
        #Layer_Target_REM = arcpy.mapping.Layer(ggl_raster + "_ADJUSTED" + target_re + "m")
        #Layer_Volume_Table = arcpy.mapping.Layer(out_table)
        #arcpy.mapping.AddLayer(df, Layer_Volume_Table)

        #Overwrite existing Volumes
        arcpy.DeleteField_management(zone_poly, ["MEAN", "STD", "SUM", "COUNT"])

        #arcpy.AddJoin_management (in_zone_data, zone_field, out_table, zone_field, 'KEEP_ALL')

        #Join zonal statistics to zone polygon
        arcpy.JoinField_management(zone_poly, zone_field, out_table, zone_field, ["SUM", "MEAN", "STD", "COUNT"])
        #arcpy.CalculateField_management(in_zone_data, "SUM", 'round(!SUM!, 0)', "PYTHON")
        #arcpy.CalculateField_management(in_zone_data, "STD", 'round(!STD!, 1)', "PYTHON")
        #arcpy.CalculateField_management(in_zone_data, "MEAN", 'round(!MEAN!, 1)', "PYTHON")
        #arcpy.CalculateField_management(in_zone_data, "MEAN", 'round(!MEAN!, 1)', "PYTHON_9.3")
        arcpy.AddMessage("Go Beavs!!!")
        #arcpy.AddField_management(in_zone_data, "Adjusted", 'LONG' )

        #arcpy.CalculateField_management(in_zone_data, "Adjusted", expression, "PYTHON_9.3")
        arcpy.AddMessage("Creating CSV...")
        arcpy.TableToTable_conversion(out_table, dir, csv)
        return
