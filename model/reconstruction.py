def load_image(path):
    """ load the image as black and white

    Args:
        path: a string with path to image to be load
    Returns:
        img: a ndarray for orginal image in grayscale, purely black(0) and white(255)
        thresh: a ndarray for orginal image in grayscale with invert colour, purely black(0) and white(255)
    """
    img = cv2.imread(path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # convert image to grayscale
    ret, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)  # convert image to solely black (0) and white (255) in invert colour
    ret2, img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    return img,thresh


def contour_info(thresh,contours):
    """ find the position information for each contour in the image

    Args:
        thresh: a ndarray in grayscale with invert colour
        contours: a list contain points for each contour
    Returns:
        start_x: a list with the starting x position for each contour, stored form left to right
        info: a list position info for each contour, stored form left to right. Format: contour_idx, width, starting_y, height
    """
    by_x = {} # position info for segments with starting x position as key

    for i in range(len(contours)):
      x, y, w, h = cv2.boundingRect(contours[i]) # getting position info for each contour
      if x in by_x.keys():
        if(isinstance(by_x[x][0],list)):
          by_x[x] = sum(by_x[x], [])
        by_x[x] = [by_x[x],[i, w, y, h]]
      else:
        by_x[x] = [i, w, y, h]


    by_x_sort = sorted(by_x.items()) # sort the contours from left to right

    start_x,info = [],[]
    for pos in by_x_sort:
      if(isinstance(pos[1][0],list)):
          for inf in pos[1]:
            start_x.append(pos[0])
            info.append(inf)
      else:
          start_x.append(pos[0])
          info.append(pos[1])
 
    return start_x, info


def find_seg(start_x, info):
    """ combine contours for each math symbol

    Args:
        start_x: a list with the starting x position for contours
        info: a list position info for each contour
    Returns:
        crop: a list for position info for individual symbol. Format: starting_x, width, starting_y, height, contour_idx
    """
    crop = [] 
    combined = [] # list to store index of combined contour

    crop_idx = 0 # current index of segment

    for i in range(len(info)):
        # skip this contour if is combined with previous contours
        if (info[i][0] in combined): 
            continue
        crop.append([start_x[i], info[i][1], info[i][2], info[i][3],[info[i][0]]]) # format: x,w,y,h,i

        # check all contour on the left to see if need to combine
        for j in range(i + 1, len(start_x)):

            # check if start at almost same x position and if width is similar
            if ((start_x[j] - start_x[i]) <= info[i][1] / 2):
                if (abs(info[i][1] - info[j][1]) < (max(info[i][1], info[j][1]) / 2.5)):
                
                    crop[crop_idx][1] = max(crop[crop_idx][1] + crop[crop_idx][0], info[j][1] + start_x[j]) - crop[crop_idx][0]
                    if (crop[crop_idx][2] < info[j][2]):
                        crop[crop_idx][3] = info[j][2] - crop[crop_idx][2] + info[j][3]
                    else:
                        crop[crop_idx][3] += crop[crop_idx][2] - info[j][2]
                        crop[crop_idx][2] = info[j][2]

                    crop[crop_idx][4].append(info[j][0])
                    combined.append(info[j][0])
            # stop checking if this contour is already far enough
            else:
              break
        crop_idx += 1
    return crop


def crop_seg(crop, img, thresh, contours):
    """ crop each symbol from orginal image

    Args:
        crop: a list for position info for each symbol
        img: a ndarray for orginal image in grayscale
        thresh: a ndarray for orginal image in grayscale, with invert colour
        contours: a list contain points for each contour
    Returns:
        segments: a list to store each symbol as grayscale
    """
    segments = [] 

    for seg in crop:
        # clear everything except current segemnt
        white_img = np.full((img.shape[0], img.shape[1]), 0, dtype='uint8')
        for idx in seg[4]:
          inv_color = thresh.copy()
          cv2.drawContours(inv_color, contours, idx, 0, -1)
          white_img += cv2.bitwise_not(inv_color+img)
    
        white_img = cv2.bitwise_not(white_img)
    
        symbol = white_img[seg[2]:seg[2] + seg[3], seg[0]:seg[0] + seg[1]]        

        # pad current segment if is too thin 
        if (symbol.shape[0] < symbol.shape[1] / 2.5):
            white = np.full((int((seg[1] - symbol.shape[0]) / 2), symbol.shape[1]), 255, dtype='uint8')
            symbol = np.vstack([white, symbol, white])
        elif (symbol.shape[1] < symbol.shape[0] / 2):
            white = np.full((symbol.shape[0], int((symbol.shape[0] - symbol.shape[1]) / 2)), 255, dtype='uint8')
            symbol = np.c_[white, symbol, white]
    
        segments.append(symbol)

    return segments

def get_result(crop, segments):
    """ pass each segment to model and get the recoginzed equation

    Args:
        crop: a list for position info for each symbol
        segments: a list to store each symbol as grayscale
    Returns:
        result: a string that represent the equation in LaTex
    """
    result = ""
    exp = 0 # if currently is exponent 
    exp_end  = False
    sqrt = 0 # if currently in squart root
    sqrt_end = []
    bottom = 0 # if currently in lower part
    bottom_end = False

    for i in range(len(segments)):
      # enter exponent if current is above previous

      current_seg = cv2.cvtColor(segments[i],cv2.COLOR_GRAY2RGB)
      current_seg = Image.fromarray(current_seg)
      current_seg = data_transform(current_seg)

      current_seg = AlexNet.features(current_seg).cuda()

      pred = labels_map[model(current_seg).max(1, keepdim=True)[1]]

      if (i > 0 and not bottom_end
          and (crop[i][2] + crop[i][3] < crop[i - 1][2] + crop[i - 1][3] * 0.5)):
        result += '^{'
        exp += 1
      
      if (i > 0 and not exp_end
          and (crop[i][2]  > crop[i - 1][2] + crop[i - 1][3] * 0.5)):
        result += '_{'
        bottom += 1

      result += pred

      if(pred=='\sqrt{'):
        sqrt_end.append(crop[i][0] + crop[i][1])
        sqrt += 1
        if( i>0 and crop[i - 1][0] + crop[i - 1][1]>crop[i][0]):
          result = result[0:len(result)-7]+'\sqrt['+result[len(result)-7]+']{'

      elif(pred == 'n'):
        if(result[len(result)-2:]=='si'):
          result = result[:len(result)-2]+"\sin"
        elif(result[len(result)-2:]=='ta'):
          result = result[:len(result)-2]+"\tan"
      elif(pred == 's'):
        if(result[len(result)-2:]=='co'):
          result = result[:len(result)-2]+"\cos"

      elif(pred == 'g'):
        if(result[len(result)-2:]=='lo'):
          print(result)
          result = result[:len(result)-2]+"\log"


      exp_end = False
      bottom_end = False
      if(pred==',' and exp == True):
        result = result[0:len(result)-3]+'\prime'
        exp = False
        exp_end = True
      
      if (bottom):
        if (i + 1 == len(segments)):
          for num in range(bottom):
            result += '}'
        elif (crop[i][2]> crop[i + 1][2] + crop[i + 1][3] * 0.5):
          result += '}'
          bottom -= 1
          bottom_end = True
      
      if (exp):
        if (i + 1 == len(segments)):
          for num in range(exp):
            result += '}'
        elif (crop[i][2] + crop[i][3] < crop[i + 1][2] + crop[i + 1][3] * 0.5):
          result += '}'
          exp -= 1
          exp_end = True

      if(sqrt):
        if (i + 1 == len(segments)):
          for num in range(sqrt):
            result += '}'
        elif (crop[i+1][0]>=sqrt_end[sqrt-1]):
          sqrt -= 1
          result+='}'
      

    return result

def show_img(images):
    """ display each image of equation/segment in grayscale

    Args:
        images: a list to store pixel of each image
    """
    i = 0
    row = math.ceil(len(images)/5)
    for im in images:
      plt.subplot(row,5, i + 1)
      plt.imshow(im, 'gray', vmin=0, vmax=255)
      plt.title(i)
      plt.xticks([])
      plt.yticks([])
      i += 1
