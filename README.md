# Geomorphic Grade Line Relative Elevation Model
## Version 2.1
### Last Updated: 05/03/2020
### ArcMap Python Toolbox

![gglrem_thumb](https://user-images.githubusercontent.com/29985018/44356381-0e653a00-a464-11e8-91fb-788c0ebc08dd.png)

## Version 2.1 Updates!!
-The Step 6 should now work without issue. 
-The tool will generate volumes for each Cut/Fill polygon with a unique ID.
-User should be able to use any polygon feature class or shapefile, not just product from Step 5.

## Getting Started:

- Should run on ArcGIS 10.x ; built on Python 2.7
- Will not run in ArcGIS Pro ; built on Python 3.x
- Download the toolbox zip and unzip contents to your project folder.
- Version 2.0 adds Steps 5 & 6 as an experimental Cut/Fill volume calculator. It is likely buggy.
- The rest of this README has not been updated since the release of Version 2.0.  


![gglremtool](https://user-images.githubusercontent.com/29985018/44349484-fb496e80-a451-11e8-8dd1-e9a31d1bb486.png)

## Report Issues

This tool is a product of many google searches and trial and error. Keep in mind that there are likely bugs.
If the user encounters any problems running the GGLREM tool please email Matt Helstab at joseph.helstab@usda.gov.

## GGLREM Tool

- Create Centerline

  #### REQUIRED: DEM 

  This first steps ensures that the users workspace and coordinate system is correctly set before creating a polyline feature class. The     user must then start an edit session and draw their valley centerline. The RouteID field in the Centerline polyline must be named.   
  
  ![step1](https://user-images.githubusercontent.com/29985018/44349907-00f38400-a453-11e8-972f-eb3131e190ed.png)

- Create Cross Sections

   #### REQUIRED: Centerline feature class
  
  Select Route ID Field and Route ID (ensures proper workflow) and set the distance perpendicular to the centerline you'd like to extend     the cross sections to. Finally, choose the direction you'd like to build cross sections from. 
  
  ![step2](https://user-images.githubusercontent.com/29985018/44349912-0650ce80-a453-11e8-9058-897cd2206103.png)

- Create GGL Table and Centerline Stations

   #### REQUIRED: Routed Centerline feature class; Cross Section feature class; DEM
   
   Input Routed Centeline feature class and the Route ID. Input the Cross Section feature class. Set centerline buffer distance            (*OPTIONAL*). Input DEM.
   
   ![step3](https://user-images.githubusercontent.com/29985018/44349921-08b32880-a453-11e8-8fea-8171e86d0d3b.png)

- Create Relative Elevation Model(s)

   #### REQUIRED: Cross Section feature class; GGL Table from Step 3, or a custom modeled GGL; DEM 

  Evaluate the GGL Table and choose the model that best fits the project target surfaces. (*A user created model can be used to detrend   the valley*). Choose the output Relative Elevation Model(s) to produce. 
  
  ![step4](https://user-images.githubusercontent.com/29985018/44349926-0b158280-a453-11e8-8070-067edae73b90.png)
