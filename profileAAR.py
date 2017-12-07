# -*- coding: utf-8 -*-
"""
/***************************************************************************
 profileAAR
                                 A QGIS plugin
 profileAAR des
                              -------------------
        begin                : 2017-08-31
        git sha              : $Format:%H$
        copyright            : (C) 2017 by Moritz Mennenga & Kay Schm�tz / NIhK WHV / UFG CAU KIEL / ISAAKiel
        email                : mennenga@nihk.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QPixmap
from qgis.core import *  # QgsMessageLog, QgsVectorDataProvider - Import changed to use the full geometry options
from qgis.gui import QgsMessageBar, QgsMapLayerComboBox, QgsMapLayerProxyModel
from qgis.utils import showPluginHelp

# Initialize Qt resources from file resources.py
import resources
import sys
# errorhandling is managed here
from src.handlers.ErrorHandler import ErrorHandler, CoordReader
from src.data_objects.Coordinates import Coordinates

from src.gis_api.Logger import Logger
from src.gis_api.MessageWrapper import MessageWrappper
from src.gis_api.Point import Point
from profiletransformer import ProfileTransformer, CoordinatesTransformer, SlopeCalculator

# the export to a shapefile happens here
from export import Export

# Import the code for the dialog
from profileAAR_dialog import profileAARDialog
import os.path


class profileAAR:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'profileAAR_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&profileAAR')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'profileAAR')
        self.toolbar.setObjectName(u'profileAAR')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('profileAAR', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/profileAAR/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'profileAAR'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&profileAAR'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def layer_field(self):
        '''Function to read the Fieldnames in the select infos in GUI section'''
        # get the selected layer from the inputCombobox
        selectedLayer = self.dlg.inputCombo.currentLayer()
        # Identify fields of the selected layer
        fields = selectedLayer.pendingFields()
        # Get field names of the fields
        fieldnames = [field.name() for field in fields]
        # Clear zCombo
        self.dlg.zCombo.clear()
        # Add field names to zCombo
        self.dlg.zCombo.addItems(fieldnames)
        # same for the view column
        self.dlg.viewCombo.clear()
        self.dlg.viewCombo.addItems(fieldnames)
        # and for the profile column
        self.dlg.profileCombo.clear()
        self.dlg.profileCombo.addItems(fieldnames)

    def run(self):

        self.dlg = profileAARDialog()
        coord_reader = CoordReader()
        error_handler = ErrorHandler(MessageWrappper(self.iface), Logger(pluginName='profileAAR'), coord_reader)
        slope_calculator = SlopeCalculator()
        profile_transformer = ProfileTransformer(coord_reader, CoordinatesTransformer(slope_calculator),
                                                   slope_calculator, error_handler)
        export = Export(self.iface)

        self.setOutputPath()
        '''SELECT INPUT IN GUI'''
        # CHOOSE INPUT LAYER
        # read layers from qgis layers and filter out the pointlayers to display in the input combobox
        self.dlg.inputCombo.setFilters(QgsMapLayerProxyModel.PointLayer)
        # CHOOSE COLUMNS FOR Z-VALUE, VIEW AND PR-NUMBER
        # CALLS FUNCTION LAYER_FIELD (once on startup on activation, to enable using when only one point fc is present)
        self.dlg.inputCombo.activated.connect(self.layer_field)
        self.dlg.inputCombo.currentIndexChanged.connect(self.layer_field)

        self.dlg.helpButton.clicked.connect(self.show_help)

        '''SHORT BLOCK OF PLUGIN CODE (runs the dialog and triggers the event after the OK button was pressed)'''
        # create/show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            # Check if input fields are filled correctly an if the layer has correct properties
            error_handler.input_check(self.dlg.outputPath.text())

            '''GET INPUT FROM GUI TO VARIABLES/PREPARE LIST OF DATA'''
            # GET TEXT FROM METHOD AND DIRECTION
            # Read the method that is selected
            method = unicode(self.dlg.methodCombo.currentText())
            # read the direction, that is selected
            direction = unicode(self.dlg.directionCombo.currentText())
            # Get the selected layer
            selectedLayer = self.dlg.inputCombo.currentLayer()
            # PREPARE DATA LIST
            # TODO: Check columns for fieldtypes, z has to be float etc.
            # Go thought all data rows in the selected layer
            featureList = selectedLayer.getFeatures()

            # list for the data
            coordList = []  # type: List[Coordinates]

            # list for the different profile names
            profile_names = []
            # check if the z values have the correct type and if the crs is projected
            error_handler.field_check(selectedLayer, self.dlg.zCombo.currentText())
            #error_handler.messageOutput.printError(feature[self.dlg.zCombo.currentText()])


            for feature in featureList:
                # retrieve every feature with its geometry and attributes
                # fetch geometry
                geom = feature.geometry()

                coordList.append(
                    Coordinates(
                        Point(geom.asPoint(), feature[self.dlg.zCombo.currentText()]),
                        feature[self.dlg.viewCombo.currentText()],
                        feature[self.dlg.profileCombo.currentText()]))

                # write a list of profilenames (unique entries)
                if feature[self.dlg.profileCombo.currentText()] not in profile_names:
                    profile_names.append(feature[self.dlg.profileCombo.currentText()])

            '''WORK ON EVERY PROFILE IN LOOP'''
            # CREATE A LIST OF DATA FOR EVERY PROFILE
            # select every single profile in a loop

            coord_trans = []
            for profile_name in profile_names:
                # instantiate a temporary list for a single profile
                coord_proc = []
                # instantiate list for the view to check if all entries in one profile are the same
                view_check = []
                # iterate through the features in coord, if the profilename matches store the features datalist in templist
                for coordinate in coordList:
                    """:type coordinate: Coordinates"""
                    if coordinate.profile_name == profile_name:
                        coord_proc.append(coordinate)
                        # write the unique view values in the checklist
                        if coordinate.view_name not in view_check:
                            view_check.append(coordinate.view_name)

                # Handle Errors depending on the attributes in the fields
                # Errorhandling: Checking the single Profiles for inconsestency
                # Therefore we need the data of the actual profile, the view_check with the view values and actual profile name
                error_handler.checkViews(view_check, profile_name)
                error_handler.checkCoords(coord_proc, profile_name)

                # Calculating the profile and add it to the list
                coord_trans.append(profile_transformer.transformation(coord_proc, method, direction))
                # QgsMessageLog.logMessage(str(slope), 'MyPlugin')

            '''Export the data'''
            # For exporting we need the data, the path and the crs of the input data
            export.export(coord_trans, self.dlg.outputPath.text(), selectedLayer.crs())
            # Load the file to qgis automaticly
            layer = self.iface.addVectorLayer(self.dlg.outputPath.text(), "", "ogr")
            # if the loading of the layer fails, give a message
            error_handler.checkLayer(layer)

            # TODO: Standartfehler o.ä. Warnung - Christoph


            pass

    def setOutputPath(self):
        self.dlg.outputPath.clear()
        # Choose file if button is clicked
        self.dlg.outputButton.clicked.connect(self.select_output_file)

    def select_output_file(self):
        filename = QFileDialog.getSaveFileName(self.dlg, "Select output file ", "", '*.shp')
        self.dlg.outputPath.setText(filename)

    def show_help(self):
        showPluginHelp()
