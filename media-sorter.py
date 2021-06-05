import os, os.path, time, sys, datetime, csv
from os import close
from PIL import Image
from PIL.ExifTags import TAGS
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from pathlib import Path

# test source and target directories
sourceDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\source"
targetBaseDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\target"
# default date format
dateFormat = '%Y-%m-%d'
# we will overwrite the target files by default
overwriteFiles = True
#supported image formats
imgFormats = ['png', 'jpg', 'jpeg']
#supported video formats
videoFormats = ['m4v', 'mov', 'mp4']
DATE_TIME_ORIG_TAG = 36867

recurringDays = []
specialDays = []


def get_field (exif,field) :
  for (k,v) in exif.items():
     if TAGS.get(k) == field:
        return v

# extracts dates from the media files. We retrive creation date, modification and date taken
def get_dates(filePath, fileName):
    dates = {}
    # print(filePath)
    dates["creation_date"]  = datetime.datetime.strptime(time.ctime(os.path.getctime(filePath)), "%c")
    dates["modification_date"]  = datetime.datetime.strptime(time.ctime(os.path.getmtime(filePath)), "%c")
    dates["date_taken"] = ""
   
   # for supported image files lets extract exif information
    if fileName.split('.')[1].lower() in imgFormats:  
        try:
            with Image.open(filePath) as im:
                exif =  im._getexif()
                if DATE_TIME_ORIG_TAG in exif:
                    datestr = exif[DATE_TIME_ORIG_TAG]
                    dates["date_taken"]  = datetime.datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")
        except :
            print("unable to read exif information for ", filePath)  
    # for supported video files lets extract metatdata
    elif fileName.split('.')[1].lower() in videoFormats:
        parser = createParser(filePath)
        if parser:
            with parser:
                try:
                    metadata = extractMetadata(parser)
                except Exception as err:
                    print("Metadata extraction error: %s" % err)
                    metadata = None
            if metadata:
                dates["date_taken"]  = metadata.get('creation_date')
            else:
                print("unable to read exif information for ", filePath)   
        else:
            print("unable to read exif information for ", filePath)           
    #everything else just defaults to creation date
    else:
        print("EXIF NOT SUPPORTED FOR  ", filePath)   
    
    return dates


#moves files after creating target dreictory. It will prepend the target directory with any
# string provided in preString parameter 
def moveFile(filePath, file, dirName, preString=""):
    if(preString != ""):
        dirName = preString + "-" + dirName
    targetDir = os.path.join(targetBaseDir, dirName)
    Path(targetDir).mkdir(parents=True, exist_ok=True)
    target = os.path.join(targetDir,file)
    try:
        Path(filePath).rename(target)
    except WindowsError:
        os.remove(target)
        Path(filePath).rename(target)
    
    print(filePath, " ==>  ", targetDir)



# generic date comparer method. It will compare dates in MM/DD format by default
# if includeYearsInComparison set to True it will use the date format YYYY/MM/DD 
def dateComparer(recurringDay, dateToCheck, includeYearsInComparison=False):

    #for recurring day comparision we consider only month and day
    format = "%m/%d"

    if includeYearsInComparison:
        #for special day comparision we consider year, month and day
        format = dateFormat
    return (recurringDay['day'].strftime(format) == dateToCheck.strftime(format))



def checkDay(dateList, dateToCheck, includeYearsInComparison=False):
    if(dateToCheck == ""):
        return []
    return list(filter(lambda d:dateComparer(d, dateToCheck, includeYearsInComparison) , dateList))



# sort a file either based on recurring days or special day. by default it will sort based on recurring day
# 
def sortRecurringAndSpecialDayFiles(root, file, filePath, dates, specialDay):
    #finds point of interest date and then moved based on date_taken, modification date and creation date in that order
     #check for exif data
    dateList = recurringDays
    if(specialDay):
        print("special day ")
        dateList = specialDays

    poiDay = checkDay(dateList, dates["date_taken"], specialDay)
    if(len(poiDay) == 1):
        moveFile(filePath, file, poiDay[0]['dirName'], dates["date_taken"].strftime(dateFormat))
        return True
    
    #check for modification date
    poiDay = checkDay(dateList, dates["modification_date"], specialDay)
    if(len(poiDay) == 1):
        moveFile(filePath, file, poiDay[0]['dirName'], dates["modification_date"].strftime(dateFormat))
        return True
    
    #finally check for creation date
    poiDay = checkDay(dateList, dates["creation_date"], specialDay)
    if(len(poiDay) == 1):
        print("moving by creation date")
        moveFile(filePath, file, poiDay[0]['dirName'], dates["creation_date"].strftime(dateFormat))
        return True
    
    return False



#simple wrapper function for sortRecurringAndSpecialDayFiles. Call
# sortRecurringAndSpecialDayFiles with specialDay parameter set to False
def moveByRecurringDay(root, file, filePath, dates):    
    return sortRecurringAndSpecialDayFiles (root, file, filePath, dates, False)



#simple wrapper function for sortRecurringAndSpecialDayFiles. Call
# sortRecurringAndSpecialDayFiles with specialDay parameter set to True
def moveBySpecialDay(root, file, filePath, dates):
    return sortRecurringAndSpecialDayFiles (root, file, filePath, dates, True)
 


 # this method will sort the media by date. order of precedence is date taken, creation date and then
 # modificaiton date    
def sortByDate(root, file, filePath, dates):

    # files does not fall under on recurring day, special day or range
    # we just move the file to a folder named with format YYYY-MM 
    # named after either date taken or created 
    if(dates["date_taken"] != ""):        
        moveFile(filePath, file, dates["date_taken"].strftime("%Y-%m"))
    elif(dates["creation_date"] != ""): 
        moveFile(filePath, file, dates["creation_date"].strftime("%Y-%m"))
    elif(dates["modification_date"] != ""): 
        moveFile(filePath, file, dates["modification_date"].strftime("%Y-%m"))
    else:
        print("ERROR - CAN'T BE SORTED - ", filePath)
        return False    
    return True



# Runs through all the files in a given source directory and processes it one by one    
def runThruFiles():
    for root, subdirs, files in os.walk(sourceDir):
        for file in os.listdir(root):
            filePath = os.path.join(root, file)
            if os.path.isfile(filePath):
               dates = get_dates(filePath, file)
               print(dates)
               if(moveBySpecialDay(root, file, filePath, dates)):
                   continue
               if(moveByRecurringDay(root, file, filePath, dates)):
                   continue
               if(sortByDate(root, file, filePath, dates)):
                   continue            
                   
               print("\n")



# reads configuration file and sets up internal data structures
def readDays():
    with open("days.csv", 'r') as data:      
        for line in csv.DictReader(data):
            # print(line)
            if "type" in line:
                if line['type'] == 'recurringDay':
                    recurringDay = {}
                    day = datetime.datetime.strptime(line['from'], '%m/%d')
                    recurringDay['day'] = day
                    recurringDay['dirName'] = line['dirName']
                    recurringDays.append(recurringDay)
                elif line['type'] == 'specialDay':
                    specialDay = {}
                    day = datetime.datetime.strptime(line['from'], '%Y/%m/%d')
                    specialDay['day'] = day
                    specialDay['dirName'] = line['dirName']
                    specialDays.append(specialDay)
    
    # print("\nRecurring Days ------ ")
    # print(recurringDays)
    # print("\nSpecial Days ------ ")
    # print(specialDays)
    

if __name__ == "__main__":
    print("sorting files ")
    readDays()
    runThruFiles()
