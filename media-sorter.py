# TODO dont create target folder inside source folder
import os, os.path, time, sys, datetime, csv, time, uuid, pprint
from os import close, error, stat
from PIL import Image
from PIL.ExifTags import TAGS
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from pathlib import Path
import logging, traceback
import timeit
import exifread
from threading import Timer
from time import sleep
from periodic import periodic_task
# import pyheif

# test source and target directories
sourceDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\source"
targetBaseDir = "S:\\Renuka\\Renuka-Data\\Personal\\learning\\python\\source\\test\\target"
defaultTargetDir = "sorted-media"

# default date format
dateFormat = '%Y-%m-%d'
dateTimeFormat = "%Y-%m-%d-%H-%M-%S"
dateYearMonthFormat = "%Y-%m"
configYMDFormat = '%Y/%m/%d'
configMDFormat = '%m/%d'
#date time tag in exif
DATE_TIME_ORIGINAL_TAG = 36867
DATE_TIME_DIGITIZED_TAG = 36868

# we will overwrite the target files by default
overwriteFiles = True

#supported image formats
imgFormats = ['png', 'jpg', 'jpeg']
heicDateTimeKey = 'EXIF DateTimeOriginal'
#supported video formats
videoFormats = ['m4v', 'mov', 'mp4']

#Log configurations
loggerName = "media-sorter-log"
baseLogFileName = loggerName + ".csv"
logFileHeader = ['Result', 'From', 'To']
logger = ""

#configuration filename
configFileName = "media-sorter-config.csv"
#configuration file with full path
configFile = ""

#global variables
recurringDays = []
specialDays = []
dateRanges = []
statsDict = {}



def formatMessage(status, source, sourceFile, targetFile="", additonalInfo="", exceptionMsg=""):
    return status + "," + source + "," + sourceFile + "," + targetFile + "," + additonalInfo + "," + exceptionMsg

def setupLogging():
    logFileName = datetime.datetime.now().strftime(dateTimeFormat) + "-" + baseLogFileName
    logFile = os.path.join(targetBaseDir, logFileName)    
    print("Logfile -", logFile)

    # create logger
    logger = logging.getLogger(loggerName)
    logger.setLevel(logging.DEBUG) # log all escalated at and above DEBUG

     # create a formatter and set the formatter for the handler.
    formatter = logging.Formatter('%(asctime)s,%(levelname)s,%(message)s')

    # add a file handler
    fh = logging.FileHandler(logFile)
    fh.setLevel(logging.DEBUG) # ensure all messages are logged to file
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # # create console handler with a higher log level
    # ch = logging.StreamHandler()
    # ch.setLevel(logging.ERROR)
    # ch.setFormatter(formatter)
    # logger.addHandler(ch)

    return logger, logFile



def get_field (exif,field) :
  for (k,v) in exif.items():
     if TAGS.get(k) == field:
        return v

# extracts exif info from image files (jpg, png)
def getImageExif(filePath):
    date_taken = ""
    try:
        with Image.open(filePath) as im:
            exif =  im._getexif()
            if exif is None:
                logger.error(formatMessage("FAILURE", "getImageExif.Image.exif.None", filePath, "", "image has no exif information"))  
                return date_taken
            tag = -1
            if DATE_TIME_ORIGINAL_TAG in exif:
                tag = DATE_TIME_ORIGINAL_TAG
            elif DATE_TIME_DIGITIZED_TAG in exif:   
                tag = DATE_TIME_DIGITIZED_TAG         
            
            if(tag != -1):
                datestr = exif[tag]            
                if '\x00' in datestr:
                    # '\x00'at the end causes the strptime to fail
                    # tried rstrip and for some reason it is not working.. 
                    datestr =''.join(datestr.split('\x00'))                
                date_taken  = datetime.datetime.strptime(datestr, "%Y:%m:%d %H:%M:%S")
            else:
                logger.error(formatMessage("FAILURE", "getImageExif.Image.exif.None", filePath, "", "image has exif information but neither 'DateTimeOriginal' nor 'DateTimeDigitized' present in exif"))  
                return date_taken
    except Exception as err:
        logger.error(formatMessage("FAILURE", "getImageExif.Image.Exception", filePath, "", "unable to read exif information", format(err.with_traceback)))  
        statsDict["totalMissingExif"] += 1
        # print(traceback.print_exc())
    return date_taken

# extracts exif info from image files (heic)
def getHeicExif(filePath):
    date_taken = ""
    with open(filePath, 'rb') as heicFile:
            tags = exifread.process_file(heicFile)
            if heicDateTimeKey in tags.keys():                
                date_taken= datetime.datetime.strptime(str(tags[heicDateTimeKey]), "%Y:%m:%d %H:%M:%S")
    return date_taken

# extracts exif info from movie files ('m4v', 'mov', 'mp4')
def getVideoExif(filePath):
    date_taken = ""
    try:
        parser = createParser(filePath)
        if not parser:
            logger.error(formatMessage("FAILURE", "getVideoExif.hachoir.parser", filePath, "", "Unable to create parser. Unable to read exif information"))
            statsDict["totalMissingExif"] += 1
            return date_taken

        with parser:
            try:
                metadata = extractMetadata(parser)
            except Exception as err:
                logger.error(formatMessage("FAILURE", "getVideoExif.hachoir.parser", filePath, "", "exception while reading exif information", format(err)))
                statsDict["totalMissingExif"] += 1
                metadata = None
        if metadata:
            date_taken = metadata.get('creation_date')
        else:
            logger.error(formatMessage("FAILURE",  filePath, "", "unable to read metadata"))    
           
    except Exception as err:
        logger.error(formatMessage("FAILURE", "getVideoExif.createParser.Exception", filePath, "", "unable to create parser", format(err)))  
  
    return date_taken


# extracts dates from the media files. We retrive creation date, modification and date taken
def get_dates(filePath, fileName):
    dates = {}
    # logger = logging.getLogger(loggerName)
    # print(filePath)
    dates["creation_date"]  = datetime.datetime.strptime(time.ctime(os.path.getctime(filePath)), "%c")
    dates["modification_date"]  = datetime.datetime.strptime(time.ctime(os.path.getmtime(filePath)), "%c")
    dates["date_taken"] = ""
   
   # for supported image files lets extract exif information
    fileExtension = os.path.splitext(fileName)[1][1:].lower()
    if fileExtension in imgFormats:  
        dates["date_taken"] = getImageExif(filePath)  
    # check for heic file
    elif fileExtension == "heic":
        dates["date_taken"] = getHeicExif(filePath)
    # for supported video files lets extract metatdata
    elif fileExtension in videoFormats:
        dates["date_taken"] = getVideoExif(filePath)
    #everything else just defaults to creation date
    else:
        logger.info(formatMessage("Information", "get_dates", filePath, "", "EXIF NOT SUPPORTED"))
        statsDict["totalMissingExif"] += 1
    
    if dates["date_taken"] == datetime.datetime(1904, 1, 1):
        #invalid exif information. ignore it
        logger.warning(formatMessage("WARNING", "get_dates", filePath, "", "invalid exif information (1904/01/01). ignoring it", ""))  
        dates["date_taken"] = ""

    # print(dates)
    return dates

def checkAndMoveFile(filePath, target):
    try:
        Path(filePath).rename(target)
        logger.info(formatMessage("SUCCESS", "checkAndMoveFile", filePath, target))  
    except FileExistsError as fileExists:
        return False, "FileExistsError"
    except Exception as err:
        statsDict["totalFailures"] += 1
        logger.error(formatMessage("FAILURE", "checkAndMoveFile.move.Exception", filePath, target, "unable to process file", format(err)))
        return False, "EXCEPTION"
    return True, "SUCCESS"

def createDuplicateFileName(fileName):
    path = Path(fileName)
    return str(path.with_name(f"{path.stem}_{'DUPLICATE'}_{uuid.uuid1()}{path.suffix}"))

#moves files after creating target dreictory. It will prepend the target directory with any
# string provided in preString parameter 
def moveFile(filePath, file, dirName, mediaDateTime, addMediaDateTimeToFolderName, additionalFolderPrefix=""):

    if(addMediaDateTimeToFolderName):
       dirName =  mediaDateTime.strftime(dateFormat) + "-" + dirName

    if additionalFolderPrefix != "":
        dirName = additionalFolderPrefix + "-" + dirName

    targetDir = os.path.join(targetBaseDir, mediaDateTime.strftime("%Y"), dirName)
    Path(targetDir).mkdir(parents=True, exist_ok=True)
    target = os.path.join(targetDir,file) 

    moveSuccess, errorCode = checkAndMoveFile(filePath, target)
    
    if not moveSuccess:
        #failed to move file. is it due to file already exising?
        if errorCode == "FileExistsError" :
            statsDict["totalDuplicates"] += 1
            #file already exists. Try moving it to duplicates folder
            duplicatesFolder = os.path.join(targetBaseDir, "duplicates")
            targetDir = os.path.join(duplicatesFolder, mediaDateTime.strftime("%Y"), dirName)
            Path(targetDir).mkdir(parents=True, exist_ok=True)
            target = os.path.join(targetDir, file)  
            moveSuccess, errorCode = checkAndMoveFile(filePath, target)
            if not moveSuccess:
                # failed to move file. File exists in duplicate folder too
                # is it due to file already exising even under duplicates folder
                if errorCode == "FileExistsError" :
                    # yeah. the file exists there too. lets jus add date time stamp to file name and try again
                    target = createDuplicateFileName(target)
                    moveSuccess, errorCode = checkAndMoveFile(filePath, target)
                    if not moveSuccess:
                        #failed again . log and move on
                        logger.error(formatMessage("FAILURE", "moveFile.move.Exception", filePath, target, "unable to process file", "Exception logged already"))
                    
                

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

    if dates["date_taken"] != "" :
        # we have exif data. We will only use this for our range comparision.
        # if exif date taken is present and does not fall in range, we don't use
        # creation and modification dates for range check. If date_taken is not present
        # then the media will be sorted based on date
        # check if exif date taken falls in our range
        poiDay = checkDay(dateList, dates["date_taken"], isSpecialDay)
        if(len(poiDay) > 0):
            moveFile(filePath, file, poiDay[0]['dirName'], dates["date_taken"], True)
            return True
    else :
        # no exif date taken data. Lets try creation date and modification date
        # check for creation date
        poiDay = checkDay(dateList, dates["creation_date"], isSpecialDay)
        if(len(poiDay) > 0):        
            moveFile(filePath, file, poiDay[0]['dirName'], dates["creation_date"], True)
            return True
    
        #finally check for modification date
        poiDay = checkDay(dateList, dates["modification_date"], isSpecialDay)
        if(len(poiDay) > 0):
            moveFile(filePath, file, poiDay[0]['dirName'], dates["modification_date"], True)
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

    if dates["date_taken"] != "" :
        # we have exif data. We will only use this for our range comparision.
        # if exif date taken is present and does not fall in range, we don't use
        # creation and modification dates for range check. If date_taken is not present
        # then the media will be sorted based on date
        # check if exif date taken falls in our range
        dateRange = isInRange(dateRanges, dates["date_taken"])
        if(len(dateRange) == 0):
            #exif date taken does not fall in range. Return false
            return False
    else:
        # no exif date taken data. Lets try creation date and modification date
        dateRange = isInRange(dateRanges, dates["creation_date"])
        if(len(dateRange) == 0):
            #finally lets try if modification date atleast falls in the given range
            dateRange = isInRange(dateRanges, dates["modification_date"])
            if(len(dateRange) == 0):
                #none of the three dates are in our range, return False
                # msg = str(dates["date_taken"])
                # msg = msg + " and " + str(dates["creation_date"]) 
                # msg = msg + " and " + str(dates["modification_date"])
                # msg = msg + " not in range"
                # logger.info(formatMessage("INFO", "sortOnRange", filePath, "", msg))
                return False

    # one of either exif date taken, creation date or modification date is within given range        
    preFix = dateRange[0]["rangeStart"].strftime(dateFormat) + "---" + dateRange[0]["rangeEnd"].strftime(dateFormat)
    # logger.info(formatMessage("INFO", "sortOnRange", filePath,"", "sorting by range"))
    moveFile(filePath, file, dateRange[0]['dirName'], dateRange[0]["rangeStart"], False,  preFix)       
    return True



 # this method will sort the media by date. order of precedence is date taken, creation date and then
 # modificaiton date    
def sortByDate(root, file, filePath, dates):

    # files does not fall under on recurring day, special day or range
    # we just move the file to a folder named with format YYYY-MM 
    # named after either date taken or created 
    if(dates["date_taken"] != ""):        
        moveFile(filePath, file, dates["date_taken"].strftime(dateYearMonthFormat), dates["date_taken"], False )
        statsDict["totalProcessedOnExifDate"] += 1
    elif(dates["creation_date"] != ""): 
        moveFile(filePath, file, dates["creation_date"].strftime(dateYearMonthFormat), dates["creation_date"], False)
        statsDict["totalProcessedOnModifiedDate"] += 1
    elif(dates["modification_date"] != ""): 
        moveFile(filePath, file, dates["modification_date"].strftime(dateYearMonthFormat),  dates["modification_date"])
        statsDict["totalProcessedOnCreationDate"] += 1
    else:
        logger.error(formatMessage("FAILURE", "sortByDate", filePath, "", "ERROR - CAN'T BE SORTED"))
        statsDict["totalFailures"] += 1
        
        return False    
    return True



# Runs through all the files in a given source directory and processes it one by one    
def processMedia(configFile, useConfigFile):

    for root, subdirs, files in os.walk(sourceDir):
        for file in os.listdir(root):
            filePath = os.path.join(root, file)
            if os.path.isdir(filePath) :
                statsDict["totalDirProcessed"] += 1
            if os.path.isfile(filePath) and filePath != configFile:
                statsDict["totalFilesProcessed"] += 1
                dates = get_dates(filePath, file)
                # print(dates)
                if useConfigFile :
                    if(moveBySpecialDay(root, file, filePath, dates)):
                        statsDict["totalSortedOnSpecialDate"] += 1
                        continue
                    if(moveByRecurringDay(root, file, filePath, dates)):
                        statsDict["totalSortedOnRecurringDate"] += 1
                        continue
                    if(sortOnRange(root, file, filePath, dates)):
                        statsDict["totalSortedOnRange"] += 1
                        continue
           
                if(sortByDate(root, file, filePath, dates)):
                    statsDict["totalSortedOnDate"] += 1
                    continue          
    print()




# reads configuration file and sets up internal data structures
def readConfiguration():
    
    configFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), configFileName)
    if not os.path.isfile(configFile):
        logger.info(formatMessage("INFORMATION", "readConfiguration", configFile, "", "Configuration file does not exist in default location. Trying under source directory "))
        configFile = os.path.join(sourceDir, configFileName)
        if not os.path.isfile(configFile):
            configFile = ""
            msg = "Config  - NOT FOUND. Files will be sorted based only on dates. order of precedence is exif_date > creation_date > modification_date"
            logger.info(formatMessage("INFORMATION", "readConfiguration", configFile, "", msg))
            print(msg)
            
            return configFile, False
    
    logger.info(formatMessage("SUCCESS", "readConfiguration", configFile, "", "Found Configuration file"))

    print("Config  -", configFile, "\n")
    with open(configFile, 'r') as data:      
        for line in csv.DictReader(data):
            # print(line)
            if "type" in line:
                if line['type'] == 'recurringDay':
                    recurringDay = {}
                    day = datetime.datetime.strptime(line['from'], configMDFormat)
                    recurringDay['day'] = day
                    recurringDay['dirName'] = line['dirName']
                    recurringDays.append(recurringDay)
                elif line['type'] == 'specialDay':
                    specialDay = {}
                    day = datetime.datetime.strptime(line['from'], configYMDFormat)
                    specialDay['day'] = day
                    specialDay['dirName'] = line['dirName']
                    specialDays.append(specialDay)
                elif line['type'] == 'range':
                    dataRange = {}
                    rangeStart = datetime.datetime.strptime(line['from'], configYMDFormat)
                    dataRange['rangeStart'] = rangeStart
                    # To has to be until the end of the specified day. 
                    temp = datetime.datetime.strptime(line['to'], configYMDFormat)                    
                    rangeEnd = datetime.datetime(temp.year, temp.month, temp.day, 23, 59, 59)
             
                    dataRange['rangeEnd'] = rangeEnd
                    dataRange['dirName'] = line['dirName']
                    dateRanges.append(dataRange)
    
    return configFile, True
    
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
    print("\ntype 'range' requires from and to column with date fromat YYYY/MM/DD. All files with any one of date taken, creation or modification date (exif_date > creation_date > modification_date) falling within the given range are moved to its own directory with name provided in 'dirName' column\n")
    print("     usage:")
    print("     media-sorter <source-directory> <target-directory>")
    print("     <source-directory> defaults to current directory")
    print("     <target-directory> defaults to 'sorted-media' and a new directory will be created. IF THE TARGET DIRECTORY EXISTS ALL EXISTING FILES WILL BE OVERWRITTEN\n")


def readCmdLine():
    n = len(sys.argv)
    if(n == 2):
        sourceDir = Path(sys.argv[1]).absolute()
        dateTimePrefix = datetime.datetime.now().strftime(dateTimeFormat) + "-"
        targetBaseDir = Path(os.path.join(Path(sourceDir).parent.absolute(), dateTimePrefix + defaultTargetDir)).absolute()
    elif(n == 3):
        sourceDir = Path(sys.argv[1]).absolute()
        targetBaseDir = Path(sys.argv[2]).absolute()
    else:
        printHelp()
        
    # create target directory
    Path(targetBaseDir).mkdir(parents=True, exist_ok=True)
    
    return sourceDir, targetBaseDir

def init():
    statsDict = {
    "startTime" : timeit.default_timer(),
    "endTime" : 0,
    "totalFilesProcessed": 0,
    "totalDirProcessed":0,
    "totalFailures" : 0,
    "totalMissingExif" : 0,
    "totalDuplicates" : 0,
    "totalProcessedOnExifDate" : 0,
    "totalProcessedOnModifiedDate" : 0,
    "totalProcessedOnCreationDate" : 0,
    "totalSortedOnSpecialDate" : 0,
    "totalSortedOnRecurringDate" : 0,
    "totalSortedOnDate" : 0,
    "totalSortedOnRange" : 0
    }
    return statsDict

# calculates and returns a formatted execution time
# if endTime is given then it will use that. Otherwise it will retreive the end time from statistics dictionary
# endtime is timeit.default_timer()
def getExecutionTime(endTime=""):
    if endTime == "":
        endTime = statsDict["endTime"] 
    executionTime = endTime - statsDict["startTime"]

    # output running time in a nice format.
    mins, secs = divmod(executionTime, 60)
    hours, mins = divmod(mins, 60)

    return ("%d:%d:%d" % (hours, mins, secs))

def printStatistics():
    
    # print("\nHere are the statsDict ... \n",statsDict, "\n")
    print()
    msg = "total directories processed - {0}".format(statsDict["totalDirProcessed"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "total files processed - {0}".format(statsDict["totalFilesProcessed"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "successfully sorted - {0}".format(statsDict["totalFilesProcessed"] - statsDict["totalFailures"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "sorting failures - {0}".format(statsDict["totalFailures"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of duplicates - {0}".format(statsDict["totalDuplicates"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files sorted based on special date - {0}".format(statsDict["totalSortedOnSpecialDate"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files sorted based on range - {0}".format(statsDict["totalSortedOnRange"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files sorted based on recurring date - {0}".format(statsDict["totalSortedOnRecurringDate"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files sorted based on date - {0} [based on exif date ({1}) + creation date ({2}) + modification date ({3})]".format(statsDict["totalSortedOnDate"], statsDict["totalProcessedOnExifDate"], statsDict["totalProcessedOnCreationDate"], statsDict["totalProcessedOnModifiedDate"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files having VALID Exif data - {0}".format(statsDict["totalProcessedOnExifDate"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    msg = "count of media files having INVALID Exif data  - {0}".format(statsDict["totalMissingExif"])
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))

    statsDict["endTime"] = timeit.default_timer()
    msg = "total exeuction time (HH:MM:SS) - {0} ".format(getExecutionTime())
    print(msg)
    logger.info(formatMessage("SUCCESS", "printStatistics", msg, "", ""))  

    print()

    return

@periodic_task(1)
def printProgressStatus():
    msg = "\rDirectories scanned = {0}, files procssed = {1}, time = (HH:MM:SS) {2}  ".format(statsDict["totalDirProcessed"], statsDict["totalFilesProcessed"], getExecutionTime(timeit.default_timer()))
    print(msg, end="")


if __name__ == "__main__":    
    profile = False

    sourceDir, targetBaseDir = readCmdLine()
    print()
    print("Source - ", sourceDir)
    print("Target - ", targetBaseDir)

    # setup statistics gathering
    statsDict = init()

    # setup logging
    logger, logFile = setupLogging()  
    logger.info(formatMessage("SUCCESS", "__main__", str(sourceDir), "", "Source directory set"))
    logger.info(formatMessage("SUCCESS", "__main__", str(targetBaseDir), "", "Target directory set"))

    # read configuration
    configFile, useConfigFile = readConfiguration()
    
    # process all media files
    printProgressStatus()
    
    
    if profile:
        import cProfile, pstats
        profiler = cProfile.Profile()
        profiler.enable()
        processMedia(configFile, useConfigFile)
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats('tottime')
        # stats.strip_dirs()
        stats.dump_stats('profile_data')        
        stats.print_stats()   
    else:
        processMedia(configFile, useConfigFile)

        #print statistics
    printStatistics()

    print("Find complete summary in log file - ", logFile, "\n")
   