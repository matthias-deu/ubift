import jarray
import inspect
import os
import shutil
from subprocess import Popen, PIPE

from java.lang import System
from java.util.logging import Level
from java.io import File
from java.util import UUID
from org.sleuthkit.autopsy.coreutils import PlatformUtil
from org.sleuthkit.datamodel import SleuthkitCase
from org.sleuthkit.datamodel import AbstractFile
from org.sleuthkit.datamodel import Score
from org.sleuthkit.datamodel import ReadContentInputStream
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute
from org.sleuthkit.datamodel.TskData import TSK_DB_FILES_TYPE_ENUM
from org.sleuthkit.autopsy.ingest import IngestModule
from org.sleuthkit.autopsy.ingest.IngestModule import IngestModuleException
from org.sleuthkit.autopsy.ingest import DataSourceIngestModule
from org.sleuthkit.autopsy.ingest import FileIngestModule
from org.sleuthkit.autopsy.ingest import GenericIngestModuleJobSettings
from org.sleuthkit.autopsy.ingest import IngestModuleIngestJobSettingsPanel
from org.sleuthkit.autopsy.ingest import IngestModuleFactoryAdapter
from org.sleuthkit.autopsy.ingest import IngestMessage
from org.sleuthkit.autopsy.ingest import IngestServices
from org.sleuthkit.autopsy.coreutils import Logger
from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.autopsy.casemodule.services import Services
from org.sleuthkit.autopsy.casemodule.services import FileManager
from org.sleuthkit.autopsy.datamodel import ContentUtils
from org.sleuthkit.autopsy.casemodule.services import Blackboard
from org.sleuthkit.datamodel import Score
from java.util import Arrays

from javax.swing import JCheckBox
from javax.swing import JList
from javax.swing import JTextArea
from javax.swing import BoxLayout
from javax.swing import JLabel
from javax.swing import JTextField
from javax.swing.event import DocumentListener
from java.awt import GridLayout
from java.awt import BorderLayout
from java.awt.event import KeyListener, KeyAdapter
from javax.swing import BorderFactory
from javax.swing import JToolBar
from javax.swing import JPanel
from javax.swing import JFrame
from javax.swing import JScrollPane
from javax.swing import JComponent
from java.awt import Dimension
from java.awt import FlowLayout
from java.awt import CardLayout

# Factory that defines the name and details of the module and allows Autopsy
# to create instances of the modules that will do the analysis.
class UBIFSDataSourceIngestModuleFactory(IngestModuleFactoryAdapter):

    moduleName = "UBIFS File Recovery"

    def __init__(self):
        self.settings = None

    def getModuleDisplayName(self):
        return self.moduleName

    def getModuleDescription(self):
        return "A Module based on the UBI Forensic Toolkit (UBIFT) which allows to recover files from a raw flash image containing instances of UBIFS. For deeper inspection of UBIFS instances, please use UBIFT directly."

    def getModuleVersionNumber(self):
        return "1.0"

    def isDataSourceIngestModuleFactory(self):
        return True

    def createDataSourceIngestModule(self, ingestOptions):
        return UBIFSDataSourceIngestModule(self.settings)
        
    def getDefaultIngestJobSettings(self):
        return GenericIngestModuleJobSettings()

    def hasIngestJobSettingsPanel(self):
        return True

    def getIngestJobSettingsPanel(self, settings):
        self.settings = settings
        return UBIFSFileRecoverySettingsPanel(self.settings)    


# Data Source-level ingest module.  One gets created per data source.
class UBIFSDataSourceIngestModule(DataSourceIngestModule):
    _logger = Logger.getLogger(UBIFSDataSourceIngestModuleFactory.moduleName)

    def log(self, level, msg):
        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)

    def __init__(self, settings):
        self.context = None
        self.local_settings = settings

    # Where any setup and configuration is done
    # 'context' is an instance of org.sleuthkit.autopsy.ingest.IngestJobContext.
    # See: http://sleuthkit.org/autopsy/docs/api-docs/latest/classorg_1_1sleuthkit_1_1autopsy_1_1ingest_1_1_ingest_job_context.html
    def startUp(self, context):
        
        # Throw an IngestModule.IngestModuleException exception if there was a problem setting up
        # raise IngestModuleException("Oh No!")
        self.context = context
        
        # Get path to EXE based on where this script is run from.
        # Assumes EXE is in same folder as script
        # Verify it is there before any ingest starts
        if PlatformUtil.isWindowsOS():
            exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ubift.exe")
            self.ubift_path = File(exe_path)
            if not self.ubift_path.exists():
                raise IngestModuleException("ubift Windows executable was not found in module folder")
        elif PlatformUtil.getOSName() == 'Linux':
            exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ubift")
            self.ubift_path = File(exe_path)
            if not self.ubift_path.exists():
                raise IngestModuleException("ubift Linux executable was not found in module folder")

    # Where the analysis is done.
    # The 'dataSource' object being passed in is of type org.sleuthkit.datamodel.Content.
    # See: http://www.sleuthkit.org/sleuthkit/docs/jni-docs/latest/interfaceorg_1_1sleuthkit_1_1datamodel_1_1_content.html
    # 'progressBar' is of type org.sleuthkit.autopsy.ingest.DataSourceIngestModuleProgress
    # See: http://sleuthkit.org/autopsy/docs/api-docs/latest/classorg_1_1sleuthkit_1_1autopsy_1_1ingest_1_1_data_source_ingest_module_progress.html
    def process(self, dataSource, progressBar):
        # This seems to be necessary if the Module is changed while Autopsy is running
        if self.ubift_path is None:
            self.startUp(self.context)

        eraseblockSize = self.local_settings.getSetting('eraseblockSize')
        pageSize = self.local_settings.getSetting('pageSize')
        oobSize = self.local_settings.getSetting('oobSize')
        self.log(Level.INFO, "eraseblock size: " + eraseblockSize)
        self.log(Level.INFO, "page size: " + pageSize)
        self.log(Level.INFO, "oob size: " + oobSize)
        
        progressBar.switchToIndeterminate()
        fileManager = Case.getCurrentCase().getServices().getFileManager()
        files = fileManager.findFiles(dataSource, '%%')
        
        # Create a temporary folder named AUTOPSY_UBI_{datasource id}
        temp_dir = Case.getCurrentCase().getTempDirectory()
        working_folder = os.path.join(temp_dir, "AUTOPSY_UBI_" + str(dataSource.getId()))
        self.log(Level.INFO, "Writing UBIFT temporary files to: " + working_folder)
        if os.path.exists(working_folder):
            self.postMessage("This module should only be run once. There is already a temporary folder for datasource" + str(dataSource.getId()))
            return IngestModule.ProcessResult.OK
        else:
            os.mkdir(working_folder)    
        self.log(Level.INFO, "Writing UBIFT temporary files to: " + working_folder)
        
        for file in files:          
            # Only process files of type UNALLOC_BLOCKS
            if file.getType() is not TSK_DB_FILES_TYPE_ENUM.UNALLOC_BLOCKS:
                continue

            # Check if the user pressed cancel while Autopsy was busy
            if self.context.isJobCancelled():
                return IngestModule.ProcessResult.OK

            # Since the File we want to process is a LayoutFile(virtual file), write it to the temporary
            # folder so it can be passed to UBIFT via command line
            temp_file_path = os.path.join(temp_dir, "UBI_" + str(dataSource.getId()))
            ContentUtils.writeToFile(files[0], File(temp_file_path))   
                
            # Invoke UBIFT with command 'ubift_recover'
            pipe = Popen([self.ubift_path.toString(), "ubift_recover", str(temp_file_path), "--verbose", "--blocksize", eraseblockSize, "--pagesize", pageSize, "--oob", oobSize, "--deleted", "--output", working_folder], stdout=PIPE, stderr=PIPE)
            ubift_stdout, ubift_stderr = pipe.communicate()
            
            self.create_report(dataSource, ubift_stdout + ubift_stderr)
            
            # Create one folder for every UBIFS instance in the dataSource
            for f in os.listdir(working_folder):
                path = os.path.join(working_folder, f)
                if os.path.isdir(path): 
                    virtualRootDir = Case.getCurrentCase().getSleuthkitCase().addLocalDirectory(dataSource.getId(), str(f))
                    self.add_dir_to_datasource(path, virtualRootDir)
                 
        Case.getCurrentCase().notifyDataSourceAdded(dataSource, UUID.randomUUID())
        
        return IngestModule.ProcessResult.OK
    
    # Creates a report based on a given string. For this module, the output of UBIFT is used as content for the report.
    def create_report(self, dataSource, report_content):
        report_path = os.path.join(Case.getCurrentCase().getCaseDirectory(), "Reports", "UBIFS_Report_" + str(dataSource.getId()) + ".txt")
        report = open(report_path, 'wb+')
        report.write(report_content)
        report.close()
        
        Case.getCurrentCase().addReport(report_path, UBIFSDataSourceIngestModuleFactory.moduleName, "UBIFT Recovery Report")
        
    
    # Posts a massage (shows up in top right of Autopsy)
    def postMessage(self, message):
        msg = IngestMessage.createMessage(IngestMessage.MessageType.DATA,   UBIFSDataSourceIngestModuleFactory.moduleName, message)
        IngestServices.getInstance().postMessage(msg)
    
    # Adds a directory and all of its content to a parent datasource
    def add_dir_to_datasource(self, ubift_output_path, parent):
        tsk_case = Case.getCurrentCase().getSleuthkitCase()
        for f in os.listdir(ubift_output_path):
            file_path = os.path.join(ubift_output_path, f)
            if os.path.isfile(file_path):
                # fileName, localPath, size, ctime, crtime, atime, mtime, isFile, parent
                tsk_case.addLocalFile(f, file_path, os.path.getsize(file_path), long(os.path.getctime(file_path)), long(os.path.getctime(file_path)), long(os.path.getatime(file_path)), long(os.path.getmtime(file_path)), True, parent)
            if os.path.isdir(file_path):
                new_dir = tsk_case.addLocalFile(f, file_path, os.path.getsize(file_path), long(os.path.getctime(file_path)), long(os.path.getctime(file_path)), long(os.path.getatime(file_path)),long(os.path.getmtime(file_path)), False, parent)
                self.add_dir_to_datasource(file_path, new_dir)
        
        
class UBIFSFileRecoverySettingsPanel(IngestModuleIngestJobSettingsPanel):
    _logger = Logger.getLogger(UBIFSDataSourceIngestModuleFactory.moduleName)

    def log(self, level, msg):
        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)
    
    
    def __init__(self, settings):
        if settings is None:
            self.local_settings = GenericIngestModuleJobSettings()
        else:
            self.local_settings = settings
        self.initComponents()
        self.updateSettings(None)


    def initComponents(self):       
        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))
        self.setPreferredSize(Dimension(150, 155))
    
        self.panel1 = JPanel()
        self.panel1.setPreferredSize(Dimension(25, 40))
        self.panel1.setLayout(GridLayout(0, 2, 0, 3))
        
        self.eraseblockSizeLabel = JLabel("Erase Block Size:")
        self.eraseblockSizeLabel.setEnabled(True)
        
        self.eraseblockSizeText = JTextField("auto", 20, focusGained=self.updateSettings, focusLost=self.updateSettings) 
        self.eraseblockSizeText.setEnabled(True)
        self.eraseblockSizeText.setPreferredSize(Dimension(9, 10))
        
        self.pagesizeTextLabel = JLabel("Page Size:")
        self.pagesizeTextLabel.setEnabled(True)
        self.pagesizeText = JTextField("auto", 20, focusGained=self.updateSettings, focusLost=self.updateSettings) 
        self.pagesizeText.setEnabled(True)
        self.pagesizeText.setPreferredSize(Dimension(9, 10))
        
        self.oobSizeLabel = JLabel("OOB Size:")
        self.oobSizeLabel.setEnabled(True)
        self.oobSizeText = JTextField("none", 20, focusGained=self.updateSettings, focusLost=self.updateSettings) 
        self.oobSizeText.setEnabled(True)
        self.oobSizeText.setPreferredSize(Dimension(9, 10))
        
        self.panel1.add(self.eraseblockSizeLabel)
        self.panel1.add(self.eraseblockSizeText) 
        
        self.panel1.add(self.pagesizeTextLabel) 
        self.panel1.add(self.pagesizeText) 
        
        self.panel1.add(self.oobSizeLabel) 
        self.panel1.add(self.oobSizeText) 
        
        self.add(self.panel1)
        
        self.panel2 = JPanel()
        self.noteLabel = JTextArea("Sizes are in Bytes. A value of 'auto' for the block and page size will try to auto-determine it based on UBI headers. A positive value for the OOB area will attempt to extract it before processing the image.")
        self.noteLabel.setEnabled(False)
        self.noteLabel.setLineWrap(True)
        self.noteLabel.setPreferredSize(Dimension(325, 100))
        self.panel2.add(self.noteLabel)
        
        self.add(self.panel2)

    def updateSettings(self, event):
        if self.local_settings is None:
            self.local_settings = GenericIngestModuleJobSettings()
    
        eraseblockSize = self.eraseblockSizeText.text
        if eraseblockSize is None or not eraseblockSize.isnumeric():
            self.local_settings.setSetting("eraseblockSize", "-1")
        else:
            self.local_settings.setSetting("eraseblockSize", eraseblockSize)
        
        pageSize = self.pagesizeText.text
        if pageSize is None or not pageSize.isnumeric():
            self.local_settings.setSetting("pageSize", "-1")
        else:
            self.local_settings.setSetting("pageSize", pageSize)
        
        oobSize = self.oobSizeText.text
        if oobSize is None or not oobSize.isnumeric():
            self.local_settings.setSetting("oobSize", "-1")
        else:
            self.local_settings.setSetting("oobSize", oobSize)
        

    # Return the settings used
    def getSettings(self):
        return self.local_settings