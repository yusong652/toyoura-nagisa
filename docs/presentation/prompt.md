  Perform a complete triaxial compression test demonstration on a cubic sample (10mm ×   
  10mm × 10mm) with 800 balls (radius 0.25-0.5mm, density 2650 kg/m³).                   
                                                                                         
  This is a demonstration task - implement the complete workflow directly without        
  preliminary testing scripts.                                                           
                                                                                         
  Sample Setup:                                                                          
  Create 6 independent wall elements manually (do NOT use box command):                  
  - 2 walls perpendicular to x-axis (left at x=0, right at x=10mm)                       
  - 2 walls perpendicular to y-axis (back at y=0, front at y=10mm)                       
  - 2 walls perpendicular to z-axis (bottom at z=0, top at z=10mm)                       
  Generate 800 balls with radius 0.25-0.5mm randomly distributed within the cubic region.
                                                                                         
  Stage 1 - Isotropic Compression:                                                       
  Apply 100 kPa confining pressure to all 6 walls using servo control. Limit the maximum 
  servo velocity to 1.0 m/s.                                                             
                                                                                         
  IMPORTANT - Servo Force Update Mechanism:                                              
  The servo control must use target FORCE (not stress directly). Calculate and update the
   target force dynamically based on current effective area:                             
  - For x-direction walls (left/right): effective_area = (y_wall_distance) ×             
  (z_wall_distance)                                                                      
  - For y-direction walls (front/back): effective_area = (x_wall_distance) ×             
  (z_wall_distance)                                                                      
  - For z-direction walls (bottom/top): effective_area = (x_wall_distance) ×             
  (y_wall_distance)                                                                      
  - Target force for each wall = target_stress (100 kPa) × effective_area                
  - Update target forces regularly during cycling as the sample compresses and wall      
  distances change                                                                       
                                                                                         
  Run in background and monitor until equilibrium is reached.                            
                                                                                         
  To check equilibrium, calculate the void ratio (void_ratio = void_volume /             
  solid_volume) from the sample geometry and ball volumes. Consider the system in        
  equilibrium when ALL THREE conditions are satisfied:                                   
  1. ALL 6 walls reach target pressure (each wall pressure within 95-105 kPa range)      
  2. Confining pressure is isotropic (all walls at approximately the same stress level)  
  3. Void ratio becomes stable (relative change |Δe/e| < 0.001, i.e., less than 0.1%     
  change over monitoring interval)                                                       
                                                                                         
  Stage 2 - Axial Shearing:                                                              
  Compress the sample axially (vertical direction) at strain rate 1.0/s to 15% strain,   
  while maintaining lateral confining pressure at 100 kPa using servo control on the 4   
  lateral walls. Continue updating servo target forces based on current effective areas  
  for the 4 lateral walls. Limit lateral wall servo velocity to 1.0 m/s. Run in          
  background and monitor progress.                                                       
                                                                                         
  Stage 3 - Results and Visualization:                                                   
  1. Plot the deviatoric stress vs axial strain curve                                    
  2. Capture the final deformed sample configuration                                     
  3. Report key results: peak deviatoric stress, final axial strain, initial and final   
  void ratio, and sample behavior                                                        
                                                                                         
  Complete the entire demonstration from model initialization to final results. 