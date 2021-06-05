import os, os.path, time, sys, datetime, csv
from os import close
from PIL import Image
from PIL.ExifTags import TAGS
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from pathlib import Path

sourceDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\source"
targetBaseDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\target"
dateFormat = '%Y-%m-%d'
overwriteFiles = True
imgFormats = ['png', 'jpg', 'jpeg']
videoFormats = ['m4v', 'mov', 'mp4']
DATE_TIME_ORIG_TAG = 36867

recurringDays = []
specialDays = []


def get_field (exif,field) :
  for (k,v) in exif.items():
     if TAGS.get(k) == field:
        return v

def get_dates(filePath, fileName):
    dates = {}
    # print(filePath)
    dates["creation_date"]  = datetime.datetime.strptime(time.ctime(os.path.getctime(filePath)), "%c")
    dates["modification_date"]  = datetime.datetime.strptime(time.ctime(os.path.getmtime(filePath)), "%c")
    dates["date_taken"] = ""
   
    if fileName.split('.')[1].lower() in imgFormats:  
        try:
            with Image.open(filePath) as im:
                exif =  im._getexif()
                if DATE_TIME_ORIG_TAG in exif:
                    datestr = exif[DATE_TIME_ORIG_TAG]
                    dates["date_taken"]  = datetime.datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")
        except :
            print("unable to read exif information for ", filePath)   
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


def checkRecurringDay(dateToCheck):
    if(dateToCheck == ""):
        return []
    return list(filter(lambda recurringDay: (recurringDay['day'].day == dateToCheck.date().day and recurringDay['day'].month == dateToCheck.date().month), recurringDays))

def moveByRecurringDay(root, file, filePath, dates):
    #check for exif data
    recurringDay = checkRecurringDay(dates["date_taken"])
    if(len(recurringDay) == 1):
        moveFile(filePath, file, recurringDay[0]['dirName'], dates["date_taken"].strftime(dateFormat))
        return True
    
    #check for exif data
    recurringDay = checkRecurringDay(dates["modification_date"])
    if(len(recurringDay) == 1):
        moveFile(filePath, file, recurringDay[0]['dirName'], dates["modification_date"].strftime(dateFormat))
        return True
    
    #check for exif data
    recurringDay = checkRecurringDay(dates["creation_date"])
    if(len(recurringDay) == 1):
        moveFile(filePath, file, recurringDay[0]['dirName'], dates["creation_date"].strftime(dateFormat))
        return True
    
    return False

def checkSpecialDay(dateToCheck):
    if(dateToCheck == ""):
        return []
    return list(filter(lambda specialDay: (specialDay['day'].day == dateToCheck.date().day and 
    specialDay['day'].month == dateToCheck.date().month and 
    specialDay['day'].day == dateToCheck.date().day), specialDays))



def moveBySpecialDay(root, file, filePath, dates):
    #check for exif data
    specialDay = checkSpecialDay(dates["date_taken"])
    if(len(specialDay) == 1):
        moveFile(filePath, file, specialDay[0]['dirName'], dates["date_taken"].strftime(dateFormat))
        return True
    
    #check for exif data
    specialDay = checkSpecialDay(dates["modification_date"])
    if(len(specialDay) == 1):
        moveFile(filePath, file, specialDay[0]['dirName'], dates["modification_date"].strftime(dateFormat))
        return True
    
    #check for exif data
    specialDay = checkSpecialDay(dates["creation_date"])
    if(len(specialDay) == 1):
        moveFile(filePath, file, specialDay[0]['dirName'], dates["creation_date"].strftime(dateFormat))
        return True
    
    return False    
    
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
        print("can't sort based ")
        return False    
    return True
       

    
def runThruFiles():
    for root, subdirs, files in os.walk(sourceDir):
        for file in os.listdir(root):
            filePath = os.path.join(root, file)
            if os.path.isfile(filePath):
               dates = get_dates(filePath, file)
            #    print(dates)
               if(moveBySpecialDay(root, file, filePath, dates)):
                   continue
               if(moveByRecurringDay(root, file, filePath, dates)):
                   continue
               if(sortByDate(root, file, filePath, dates)):
                   continue            
                   
               print("\n")

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
