import cv2
import numpy as np
from .utilities import ret_smallest_obj,ret_largest_obj,imfill


class bot_localizer():

    def __init__(self):
        # State Variables
        self.is_bg_extracted = False
        self.is_base_unit_extracted = False
        self.is_maze_extracted = False

        # Parameters storing bg information for using bg-subtraction
        self.bg_model = 0
        self.filled_maze_withoutCar = 0

        # Unit Dimension for each node in maze
        self.unit_dim = 0
        self.extracted_maze = 0 


    def extract_bg(self,frozen_maze):

        gray_maze = cv2.cvtColor(frozen_maze,cv2.COLOR_BGR2GRAY)
        edge_maze = cv2.Canny(gray_maze,50,150, None, 3) # Extracting the Edge of Canny
        cnts = cv2.findContours(edge_maze, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]# OpenCV 4.2
        filled_maze = np.zeros((frozen_maze.shape[0],frozen_maze.shape[1]),dtype=np.uint8)
        for idx,_ in enumerate(cnts):
            cv2.drawContours(filled_maze, cnts, idx, 255,-1)

        # Removing car from edge-detected obj's by removing the smallest object
        self.filled_maze_withoutCar = filled_maze.copy()
        Min_Cntr_idx = ret_smallest_obj(cnts)
        if (Min_Cntr_idx!=-1):
            self.filled_maze_withoutCar = cv2.drawContours(self.filled_maze_withoutCar, cnts, Min_Cntr_idx, 0, -1)  
            CarExtracted = np.zeros_like(filled_maze)
            CarExtracted = cv2.drawContours(CarExtracted, cnts, Min_Cntr_idx, 255, -1) 
            CarExtracted = cv2.drawContours(CarExtracted, cnts, Min_Cntr_idx, 255, 3) 
            CarExtracted_inv = cv2.bitwise_not(CarExtracted)
            frozen_maze_carless = cv2.bitwise_and(frozen_maze, frozen_maze,mask=CarExtracted_inv)
            base_clr = frozen_maze_carless[0][0]
            bg = np.ones_like(frozen_maze)*base_clr
            self.bg_model = cv2.bitwise_and(bg, bg,mask=CarExtracted)
            self.bg_model = cv2.bitwise_or(self.bg_model,frozen_maze_carless)

        # Cropping the maze ROI from the rest
        filled_maze_dilated = np.zeros_like(filled_maze)

        if cnts:
            cnts_ = np.concatenate(cnts)
            cnts_ = np.array(cnts_)
            cv2.fillConvexPoly(filled_maze_dilated, cnts_, 255)

        cnts_largest = cv2.findContours(filled_maze_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]# OpenCV 4.2
        hull = cv2.convexHull(cnts_largest[0])
        cv2.drawContours(filled_maze_dilated, [hull], 0, 255)
        [X, Y, W, H] = cv2.boundingRect(hull)
        temp = self.filled_maze_withoutCar
        temp = temp[Y:Y+H, X:X+W]
        #================================= Testing if decreasing convexhull size would eliminate faulty boundary selection ==============
        # >>>>> It did not !!! Entry and exit point still pose a problem
        #per_change = -2 # 2 percent decrease in size 
        #row_chng = int( H*(per_change/100) )
        #col_chng = int( W*(per_change/100) )
        #temp = temp[ Y-row_chng:Y+H+row_chng , X-col_chng:X+W+col_chng ]
        maze_extracted = cv2.bitwise_not(temp)
        maze_extracted = cv2.rotate(maze_extracted, cv2.ROTATE_90_COUNTERCLOCKWISE)
        if not self.is_maze_extracted:
            self.extracted_maze = maze_extracted
            self.is_maze_extracted = True


        cv2.imshow('self.extracted_maze',self.extracted_maze)
        cv2.imshow('filled_maze',filled_maze)
        cv2.imshow('bg',bg)
        cv2.imshow('self.bg_model',self.bg_model)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def localize_bot(self,curr_frame,frame_disp):

        if not self.is_bg_extracted:
            self.extract_bg(curr_frame.copy())
            self.is_bg_extracted = True

        # Performing Background subtraction to localize bot
        change = cv2.absdiff(curr_frame, self.bg_model)
        change_gray = cv2.cvtColor(change,cv2.COLOR_BGR2GRAY)
        change_bin = cv2.threshold(change_gray, 15, 255, cv2.THRESH_BINARY)[1]
        change_filled = change_bin.copy()
        imfill(change_filled)
        car_isolated,cnt_largest = ret_largest_obj(change_bin)

        # Extracting circular bounding roi
        car_circular_roi = np.zeros_like(car_isolated)
        center, radii = cv2.minEnclosingCircle(cnt_largest)
        car_circular_roi = cv2.circle(car_circular_roi, (int(center[0]), int(center[1])), int(radii+(radii*0.4)), 255, -1)
        
        _,bounding_circle_cnt = ret_largest_obj(car_circular_roi)        
        [X, Y, W, H] = cv2.boundingRect(bounding_circle_cnt)
        car_circular_roi = cv2.bitwise_xor(car_circular_roi, car_isolated)
        
        car_unit = np.zeros_like(car_isolated)
        per_ext = int(0.15 * H) # (15 % larger then the circle) on all sides
        car_unit = cv2.rectangle(car_unit, (X-per_ext,Y-per_ext), ((X+W+per_ext),(Y+H+per_ext)), 255,-1)
        prev_circleNCar = cv2.bitwise_or(car_circular_roi, car_isolated)
        car_unit = cv2.bitwise_xor(car_unit, prev_circleNCar)

        # Extracting Base Unit ==> (required for conversion to data)
        if not self.is_base_unit_extracted:
             self.unit_dim = W + per_ext
             print("Dim of Base unit are [ {} x {} ] pixels ".format(self.unit_dim,self.unit_dim))
             print("Dim of Maze is [ {} x {} ] pixels ".format(self.extracted_maze.shape[0],self.extracted_maze.shape[1]))
             self.is_base_unit_extracted = True

        # Displaying localized car and spotlight in the frame_disp
        frame_disp[car_isolated>0]  = frame_disp[car_isolated>0] + (0,64,0)
        frame_disp[car_circular_roi>0]  = (128,0,128)
        frame_disp[car_unit>0]  = (128,128,128)

        cv2.imshow("change_filled", change_filled) # displaying what is being recorded
        cv2.imshow("car_isolated", car_isolated) # displaying what is being recorded
        cv2.imshow("car_localized", frame_disp) # displaying what is being recorded