# TODO dont create target folder inside source folder
import os, os.path, time, sys, datetime, csv
from os import close
from PIL import Image
from PIL.ExifTags import TAGS
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from pathlib import Path
import logging, traceback

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
loggerName = "media-sorter-log"
logFileName = loggerName + ".csv"
logFileHeader = ['Result', 'From', 'To']
logger = ""

recurringDays = []
specialDays = []
dateRanges = []

def formatMessage(status, source, sourceFile, targetFile="", additonalInfo="", exceptionMsg=""):
    return status + "," + source + "," + sourceFile + "," + targetFile + "," + additonalInfo + "," + exceptionMsg

def setupLogging():
    # create target directory
    print("creating direcotry - ", targetBaseDir)
    Path(targetBaseDir).mkdir(parents=True, exist_ok=True)
    logFile = os.path.join(targetBaseDir, logFileName)    
    print("setting up logging -", logFile,"\n")

    # create logger
    logger = logging.getLogger(loggerName)
    logger.setLevel(logging.DEBUG) # log all escalated at and above DEBUG
    # add a file handler
    fh = logging.FileHandler(logFile)
    fh.setLevel(logging.DEBUG) # ensure all messages are logged to file

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # create a formatter and set the formatter for the handler.
    # formatter = logging.Formatter('%(asctime)s,%(name)s,%(levelname)s,%(message)s')
    formatter = logging.Formatter('%(asctime)s,%(levelname)s,%(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the Handler to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger



def get_field (exif,field) :
  for (k,v) in exif.items():
     if TAGS.get(k) == field:
        return v

# extracts dates from the media files. We retrive creation date, modification and date taken
def get_dates(filePath, fileName):
    dates = {}
    # logger = logging.getLogger(loggerName)
    # print(filePath)
    dates["creation_date"]  = datetime.datetime.strptime(time.ctime(os.path.getctime(filePath)), "%c")
    dates["modification_date"]  = datetime.datetime.strptime(time.ctime(os.path.getmtime(filePath)), "%c")
    dates["date_taken"] = ""
   
   # for supported image files lets extract exif information
    if fileName.split('.')[1].lower() in imgFormats:  
        try:
            with Image.open(filePath) as im:
                exif =  im._getexif()
                if exif is None:
                    logger.error(formatMessage("FAILURE", "get_dates.Image.exif.None", filePath, "", "image has no exif information"))  
                elif DATE_TIME_ORIG_TAG in exif:
                    datestr = exif[DATE_TIME_ORIG_TAG]
                    dates["date_taken"]  = datetime.datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")
        except Exception as err:
            logger.error(formatMessage("FAILURE", "get_dates.Image.Exception", filePath, "", "unable to read exif information", format(err)))  
            # print(traceback.print_exc())
    # for supported video files lets extract metatdata
    elif fileName.split('.')[1].lower() in videoFormats:
        parser = createParser(filePath)
        if parser:
            with parser:
                try:
                    metadata = extractMetadata(parser)
                except Exception as err:
                    logger.error(formatMessage("FAILURE", "get_dates.hachoir.parser", filePath, "", "exception while reading exif information", format(err)))
                    metadata = None
            if metadata:
                dates["date_taken"]  = metadata.get('creation_date')
            else:
                logger.error(formatMessage("FAILURE",  filePath, "", "unable to read metadata"))
        else:
            logger.error(formatMessage("FAILURE", "get_dates.hachoir.parser", filePath, "", "unable to read exif information"))         
    #everything else just defaults to creation date
    else:
        logger.error(formatMessage("FAILURE", "get_dates", filePath, "", "EXIF NOT SUPPORTED"))        
    
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
        logger.info(formatMessage("SUCCESS", "moveFile", filePath, target))  
    except Exception as err:
        logger.error(formatMessage("FAILURE", "moveFile.move.Exception", filePath, target, "unable to process file", format(err)))         
        
    




# generic date comparer method. It will compare dates in MM/DD format by default
# if includeYearsInComparison set to True it will use the date format YYYY/MM/DD 
def dateComparer(dateFromList, dateToCheck, isSpecialDay=False):

    #for recurring day comparision we consider only month and day
    format = "%m/%d"

    if isSpecialDay:
        #for special day comparision we consider year, month and day
        format = dateFormat
    return (dateFromList['day'].strftime(format) == dateToCheck.strftime(format))



def checkDay(dateList, dateToCheck, isSpecialDay=False):
    if(dateToCheck == ""):
        return []
    return list(filter(lambda d:dateComparer(d, dateToCheck, isSpecialDay) , dateList))



# sort a file either based on recurring days or special day. by default it will sort based on recurring day
# 
def sortRecurringAndSpecialDayFiles(root, file, filePath, dates, isSpecialDay):
    #finds point of interest date and then moved based on date_taken, modification date and creation date in that order
     #check for exif data
    dateList = recurringDays
    if(isSpecialDay):
        dateList = specialDays

    poiDay = checkDay(dateList, dates["date_taken"], isSpecialDay)
    if(len(poiDay) == 1):
        moveFile(filePath, file, poiDay[0]['dirName'], dates["date_taken"].strftime(dateFormat))
        return True
    
    #check for modification date
    poiDay = checkDay(dateList, dates["modification_date"], isSpecialDay)
    if(len(poiDay) == 1):
        moveFile(filePath, file, poiDay[0]['dirName'], dates["modification_date"].strftime(dateFormat))
        return True
    
    #finally check for creation date
    poiDay = checkDay(dateList, dates["creation_date"], isSpecialDay)
    if(len(poiDay) == 1):        
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
 

def isInRangeChecker(dateRange, dateToCheck):
    return (dateRange["rangeStart"] <= dateToCheck <= dateRange["rangeEnd"])

def isInRange(dateRanges, dateToCheck):
    if(dateToCheck == ""):
        return []
    return list(filter(lambda dateRange:isInRangeChecker(dateRange, dateToCheck) , dateRanges))


def sortOnRange(root, file, filePath, dates):

    #check if exif date taken falls in our range
    dateRange = isInRange(dateRanges, dates["date_taken"])
    if(len(dateRange) == 0):
        #may be creation dates falls within given range
        dateRange = isInRange(dateRanges, dates["creation_date"])
        if(len(dateRange) == 0):
            #finally lets try if modification date atleast falls in the given range
            dateRange = isInRange(dateRanges, dates["modification_date"])
            if(len(dateRange) == 0):
                #none of hte three dates are in our range, return False
                return False

    # one of either exif date taken, creation date or modification date is within given range        
    preFix = dateRange[0]["rangeStart"].strftime(dateFormat) + "---" + dateRange[0]["rangeEnd"].strftime(dateFormat)
    moveFile(filePath, file, dateRange[0]['dirName'], preFix)       
    return True



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
        logger.error(formatMessage("FAILURE", "sortByDate", filePath, "", "ERROR - CAN'T BE SORTED"))
        
        return False    
    return True



# Runs through all the files in a given source directory and processes it one by one    
def processMedia():
    for root, subdirs, files in os.walk(sourceDir):
        for file in os.listdir(root):
            filePath = os.path.join(root, file)
            if os.path.isfile(filePath):
                dates = get_dates(filePath, file)
                # print(dates)
                if(moveBySpecialDay(root, file, filePath, dates)):
                    continue
                if(sortOnRange(root, file, filePath, dates)):
                    continue
                if(moveByRecurringDay(root, file, filePath, dates)):
                    continue
                if(sortByDate(root, file, filePath, dates)):
                    continue     



# reads configuration file and sets up internal data structures
def readConfiguration():
    scriptPath = os.path.dirname(os.path.realpath(__file__))
    daysCsv = os.path.join(scriptPath, "days.csv")
    print("reading configuration data from -", daysCsv, "\n")
    with open(daysCsv, 'r') as data:      
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
                elif line['type'] == 'range':
                    dataRange = {}
                    rangeStart = datetime.datetime.strptime(line['from'], '%Y/%m/%d')
                    dataRange['rangeStart'] = rangeStart
                    # To has to be until the end of the specified day. 
                    temp = datetime.datetime.strptime(line['to'], '%Y/%m/%d')                    
                    rangeEnd = datetime.datetime(temp.year, temp.month, temp.day, 23, 59, 59)
             
                    dataRange['rangeEnd'] = rangeEnd
                    dataRange['dirName'] = line['dirName']
                    dateRanges.append(dataRange)
    
    # print("\nRecurring Days ------ ")
    # print(recurringDays)
    # print("\nSpecial Days ------ ")
    # print(specialDays)
    # print("\nRanges Days ------ ")
    # print(dateRanges)
    # print("\n")
    
def printHelp():
    print("This scripts sorts your media based on the data provided in the configuration file 'days.csv'\n")
    print("days.csv format is simple. It is a csv file with four columns 'type', 'from', 'to', 'dirName'\n")
    print("type indicate what kind of entry particular line is. Allowe values or 'recurringDay', 'specialDay' and 'range'")
    print("\ntype 'recurringDay' requires only from column with date fromat MM/DD. All files with any one of date taken, creation or modification date are moved to its own directory with name provided in 'dirName' column prepended by its year")
    print("\ntype 'specialDay' requires only from column with date fromat YYYY/MM/DD. All files with any one of date taken, creation or modification date are moved to its own directory with name provided in 'dirName' column")
    print("\ntype 'range' requires from and to column with date fromat YYYY/MM/DD. All files with any one of date taken, creation or modification date falling within the given range are moved to its own directory with name provided in 'dirName' column\n")
    print("     usage:")
    print("     media-sorter <source-directory> <target-directory>")
    print("     <source-directory> defaults to current directory")
    print("     <target-directory> defaults to 'sorted-media' and a new directory will be created. IF THE TARGET DIRECTORY EXISTS ALL EXISTING FILES WILL BE OVERWRITTEN\n")


def readCmdLine():
    n = len(sys.argv)
    if(n == 2):
        sourceDir = Path(sys.argv[1]).absolute()
        targetBaseDir = Path(os.path.join(Path(sourceDir).parent.absolute(),"sorted-media")).absolute()
    elif(n == 3):
        sourceDir = Path(sys.argv[1]).absolute()
        targetBaseDir = Path(sys.argv[2]).absolute()
    else:
        printHelp()
    
    print("Source directory - ", sourceDir)
    print("Target directory - ", targetBaseDir)
    print()   

    return sourceDir, targetBaseDir


if __name__ == "__main__":

    # read command line
    sourceDir, targetBaseDir = readCmdLine()

    # read configuration
    readConfiguration()
    
    # setup loggin
    logger = setupLogging()    
    
    # process all media files
    processMedia()

    



