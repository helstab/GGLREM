# Geomorphic Grade Line Relative Elevation Model
### ArcMap Python Toolbox


## Getting Started:

- Ensure you have ArcGIS version 10.3 or newer.
- Download the toolbox and place it in the appropriate folder folder.

Insert Tool Image

## Report Issues

If the user encounters any problems running the GGLREM tool please email Matt Helstab at jmhelstab@fs.fed.us.

## GGLREM Tool

- Create Centerline

  #### REQUIRED: DEM 

  This first steps ensures that the users workspace and coordinate system is correctly set before creating a polyline feature class. The     user must then start an edit session and draw their valley centerline. The RouteID field in the Centerline polyline must be named.   
  
  Insert Image

- Create Cross Sections

   #### REQUIRED: Centerline feature class
  
  Select Route ID Field and Route ID (ensures proper workflow) and set the distance perpendicular to the centerline you'd like to extend     the cross sections to. Finally, choose the direction you'd like to build cross sections from. 
  
  Insert Image  

- Create GGL Table and Centerline Stations

   #### REQUIRED: Routed Centerline feature class; Cross Section feature class; DEM
   
   Input Routed Centeline feature class and the Route ID. Input the Cross Section feature class. Set centerline buffer distance            (*OPTIONAL*). Input DEM.

- Create Relative Elevation Model(s)

   #### REQUIRED: Cross Section feature class; GGL Table from Step 3, or a custom modeled GGL; DEM 

  Evaluate the GGL Table and choose the model that best fits the project target surfaces. (*A user created model can be used to detrend   the valley*). Choose the output Relative Elevation Model(s) to produce. 
  
  Insert Picture
