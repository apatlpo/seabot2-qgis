# -*- coding: utf-8 -*-°
"""
/***************************************************************************
 SeabotDockWidget
                                 A QGIS plugin
 Seabot
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2018-10-31
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Thomas Le Mézo
        email                : thomas.le_mezo@ensta-bretagne.org
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

import os, time

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, QTimer, QFile, QFileInfo
from PyQt5.QtCore import QDate, QTime, QDateTime, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QTreeWidgetItem, QTableWidgetItem
from PyQt5.QtGui import QIcon

from seabot.src.layerSeabot import *
from seabot.src.layerBoat import *
from seabot.src.layerMission import *
from seabot.src.layerInfo import *

from seabot.src.mission import *
from seabot.src.iridiumIMAP import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'seabot_dockwidget_base.ui'))

class SeabotDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(SeabotDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.iface = iface

        # print(self.__dir__)
        self.setupUi(self)

        self.timer_seabot = QTimer()
        self.timer_boat = QTimer()
        self.timer_mission = QTimer()
        self.timer_IMAP = QTimer()

        self.momsn_min = 0
        self.momsn_max = 0
        self.momsn_current = 0

        self.data_log = {}

        # Layers
        self.layerSeabots = {}
        self.layerBoat = LayerBoat(self.iface)
        self.layerMissions = []
        self.layerInfo = LayerInfo()

        # DB
        self.db = DataBaseConnection()
        self.imapServer = ImapServer()
        self.mission_selected = -1
        self.mission_selected_last = -2

        ################################################################

        # Imap Update
        self.imapServer.imap_signal.connect(self.update_imap)

        ### Timer handle
        self.timer_seabot.timeout.connect(self.process_seabot)
        self.timer_seabot.setInterval(5000)
        self.timer_seabot.start()

        self.timer_boat.timeout.connect(self.process_boat)
        self.timer_boat.setInterval(1000)

        self.timer_mission.timeout.connect(self.process_mission)
        self.timer_mission.setInterval(1000)
        self.timer_mission.start()

        self.timer_IMAP.timeout.connect(self.process_IMAP)
        self.timer_IMAP.setInterval(1000)

        ### UI pushButton handle
        # Init tree Widget
        self.treeWidget_iridium.setColumnCount(2)
        self.tree_log_data = self.treeWidget_iridium.setHeaderLabels(["Parameter","Data"])

        # Config tab
        self.pushButton_boat.clicked.connect(self.enable_timer_boat)

        self.spinBox_gnss_trace.valueChanged.connect(self.update_vanish_trace)

        self.pushButton_server_save.clicked.connect(self.server_save)
        self.pushButton_server_new.clicked.connect(self.server_new)
        self.pushButton_server_delete.clicked.connect(self.server_delete)
        self.comboBox_config_email.currentIndexChanged.connect(self.select_server)
        self.pushButton_server_connect.clicked.connect(self.server_connect)

        self.checkBox_gnss_lock.stateChanged.connect(self.update_lock_view)
        self.checkBox_gnss_distance.stateChanged.connect(self.update_gnss_seabot_pose)
        self.checkBox_gnss_delete.stateChanged.connect(self.update_gnss_delete)

        # Mission tab
        self.pushButton_open_mission.clicked.connect(self.open_mission)
        self.pushButton_delete_mission.clicked.connect(self.delete_mission)
        self.listWidget_mission.currentRowChanged.connect(self.update_mission_info)

        self.init_mission_table_widget()

        # State tab
        self.pushButton_state_rename.clicked.connect(self.rename_robot)
        self.pushButton_state_previous.clicked.connect(self.previous_log_state)
        self.pushButton_state_next.clicked.connect(self.next_log_state)
        self.pushButton_state_last.clicked.connect(self.last_log_state)
        self.comboBox_state_imei.currentIndexChanged.connect(self.update_state_imei)

        # Fill list of email account
        self.update_server_list()

        self.update_robots_list()
        self.update_state_imei()

    def server_save(self, event):
        email = self.lineEdit_email.text()
        password = self.lineEdit_password.text()
        server_ip = self.lineEdit_server_ip.text()
        server_port = self.lineEdit_server_port.text()
        t_zero = self.dateTimeEdit_last_sync.dateTime().toString(Qt.ISODate)
        self.db.save_server(email, password, server_ip, server_port, t_zero, self.comboBox_config_email.currentData())
        self.update_server_list()
        return True

    def server_new(self, event):
        email = self.lineEdit_email.text()
        password = self.lineEdit_password.text()
        server_ip = self.lineEdit_server_ip.text()
        server_port = self.lineEdit_server_port.text()
        t_zero = self.dateTimeEdit_last_sync.dateTime().toString(Qt.ISODate)
        self.db.new_server(email, password, server_ip, server_port, t_zero)
        self.update_server_list()
        return True

    def server_delete(self, event):
        id_config = self.comboBox_config_email.currentData()
        self.db.delete_server(id_config)
        self.update_server_list()
        return True

    def update_server_list(self):
        self.comboBox_config_email.clear()
        email_list = self.db.get_email_list()
        for email in email_list:
            self.comboBox_config_email.addItem(str(email["config_id"]) + " - " + email["email"], email["config_id"])

    def update_robots_list(self, index_comboBox=-1):
        self.comboBox_state_imei.clear()
        robot_list = self.db.get_robot_list()
        if(len(robot_list)==0):
            return

        for robot in robot_list:
            if robot["name"] != None:
                self.comboBox_state_imei.addItem(robot["name"] + " (" + str(robot["imei"]) + ")", robot["imei"])
            else:
                self.comboBox_state_imei.addItem(str(robot["imei"]), robot["imei"])

        if index_comboBox==-1:
            self.comboBox_state_imei.setCurrentIndex(len(robot_list)-1)
        else:
            self.comboBox_state_imei.setCurrentIndex(index_comboBox)

        # Create associate track
        for robot in robot_list:
            if robot["imei"] not in self.layerSeabots:
                self.layerSeabots[robot["imei"]]=LayerSeabot(robot["imei"], robot["name"])

        for key in self.layerSeabots:
            self.layerSeabots[key].update()

    def rename_robot(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            currentIndex = self.comboBox_state_imei.currentIndex()
            text, ok = QInputDialog().getText(self, "Database update",
                                         "Robot name:", QLineEdit.Normal,
                                         self.db.get_robot_name(self.comboBox_state_imei.currentData()))
            if ok and text:
                self.db.update_robot_name(text, self.comboBox_state_imei.currentData())
                self.update_robots_list(currentIndex)
                self.layerSeabots[self.comboBox_state_imei.currentData()].name = text

    def select_server(self, index=0):
        if index != -1:
            server_id = self.comboBox_config_email.currentData()
            server_data = self.db.get_server_data(server_id)
            self.lineEdit_email.setText(str(server_data["email"]))
            self.lineEdit_password.setText(str(server_data["password"]))
            self.lineEdit_server_ip.setText(str(server_data["server_ip"]))
            self.lineEdit_server_port.setText(str(server_data["server_port"]))
            self.dateTimeEdit_last_sync.setDateTime(server_data["last_sync"])

    def open_mission(self, event):
        #options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        #options |= QFileDialog.ExistingFiles # Allow several files to be opened
        filenameList, _ = QFileDialog.getOpenFileNames(self,"Select mission file(s)", "","Mission Files (*.xml)")
        for filename in filenameList:
            print("filename=", filename)
            mission = SeabotMission(filename)
            layermission = LayerMission(mission)
            self.layerMissions.append(layermission)
            layermission.update_mission_layer()
            self.listWidget_mission.addItem(layermission.get_mission().get_mission_name())

    def delete_mission(self, event):
        mission_id = self.listWidget_mission.currentRow()
        print("mission selected = ", mission_id)
        if mission_id != -1:
            self.listWidget_mission.takeItem(mission_id)
            print(mission_id)
            print(self.layerMissions)
            del self.layerMissions[mission_id]
            print(self.layerMissions)
            self.mission_selected = self.listWidget_mission.currentRow()


    def closeEvent(self, event):
        self.timer_seabot.stop()
        self.timer_boat.stop()
        self.timer_IMAP.stop()
        self.timer_mission.stop()

        self.imapServer.stop_server()
        # self.layerSeabots.clear()
        # self.layerMissions.clear()

        self.closingPlugin.emit()
        event.accept()

    def set_enable_form_connect(self, enable):
        if(enable):
            self.comboBox_config_email.setEnabled(True)
            self.lineEdit_email.setEnabled(True)
            self.lineEdit_password.setEnabled(True)
            self.lineEdit_server_ip.setEnabled(True)
            self.lineEdit_server_port.setEnabled(True)
            self.pushButton_server_save.setEnabled(True)
            self.pushButton_server_new.setEnabled(True)
            self.pushButton_server_delete.setEnabled(True)
            self.dateTimeEdit_last_sync.setEnabled(True)
        else:
            self.comboBox_config_email.setEnabled(False)
            self.lineEdit_email.setEnabled(False)
            self.lineEdit_password.setEnabled(False)
            self.lineEdit_server_ip.setEnabled(False)
            self.lineEdit_server_port.setEnabled(False)
            self.pushButton_server_save.setEnabled(False)
            self.pushButton_server_new.setEnabled(False)
            self.pushButton_server_delete.setEnabled(False)
            self.dateTimeEdit_last_sync.setEnabled(False)

    def add_item_treeWidget(self, val1, val2=None, nb_digit=-1):
        item = None
        if(val2==None):
            text = self.data_log[val1]
        else:
            text = val2

        if nb_digit>0:
            text = round(float(text), nb_digit)
        elif nb_digit==0:
            text = int(round(float(text)))

        item = QTreeWidgetItem([str(val1), str(text)])
        self.treeWidget_iridium.addTopLevelItem(item)

    def fill_treeWidget_log_state(self):
        self.treeWidget_iridium.clear()
        self.add_item_treeWidget("message_id")
        self.add_item_treeWidget("ts", datetime.datetime.fromtimestamp(self.data_log["ts"]))
        self.add_item_treeWidget("east", nb_digit=0)
        self.add_item_treeWidget("north", nb_digit=0)
        self.add_item_treeWidget("gnss_speed", nb_digit=2)
        self.add_item_treeWidget("gnss_heading", nb_digit=0)
        self.add_item_treeWidget("safety_published_frequency", nb_digit=0)
        self.add_item_treeWidget("safety_depth_limit", nb_digit=0)
        self.add_item_treeWidget("safety_batteries_limit", nb_digit=0)
        self.add_item_treeWidget("safety_depressurization", nb_digit=0)
        self.add_item_treeWidget("enable_mission", nb_digit=0)
        self.add_item_treeWidget("enable_depth", nb_digit=0)
        self.add_item_treeWidget("enable_engine", nb_digit=0)
        self.add_item_treeWidget("enable_flash", nb_digit=0)
        self.add_item_treeWidget("battery0", nb_digit=2)
        self.add_item_treeWidget("battery1", nb_digit=2)
        self.add_item_treeWidget("battery2", nb_digit=2)
        self.add_item_treeWidget("battery3", nb_digit=2)
        self.add_item_treeWidget("pressure", nb_digit=0)
        self.add_item_treeWidget("temperature", nb_digit=1)
        self.add_item_treeWidget("humidity", nb_digit=2)
        self.add_item_treeWidget("waypoint", nb_digit=0)
        self.add_item_treeWidget("last_cmd_received")

    def update_state_info(self):
        # Get current momsn
        self.momsn_current = self.db.get_momsn_from_message_id(self.data_log["message_id"])

        # Update Text
        self.label_state_info.setText(str(self.momsn_current) + "/ [" + str(self.momsn_min) + ", " + str(self.momsn_max) + "]")

        # Update view of log
        self.layerInfo.update(self.data_log["message_id"])

    def update_momsn_bounds(self):
        self.momsn_min, self.momsn_max = self.db.get_bounds_momsn(self.comboBox_state_imei.currentData())

    def update_vanish_trace(self, value):
        if(value==-1):
            self.layerBoat.set_nb_points_max(value, False)
        else:
            self.layerBoat.set_nb_points_max(value, True)

    def init_mission_table_widget(self):
        self.tableWidget_mission.setColumnCount(5)
        self.tableWidget_mission.setHorizontalHeaderLabels(["Depth","D start", "D end", "T start", "T end"])

    ###########################################################################
    ### Handler Button

    def enable_timer_boat(self):
        if(self.pushButton_boat.isChecked()):
            self.layerBoat.start()
            self.timer_boat.start()
        else:
            self.timer_boat.stop()
            self.layerBoat.stop()

    def server_connect(self):
        # self.pushButton_server_connect.setStyleSheet("background-color: red")
        if(self.pushButton_server_connect.isChecked()):
            self.set_enable_form_connect(False)
            self.imapServer.set_server_id(self.comboBox_config_email.currentData())

            ## Thread IMAP
            self.imapServer.start_server()

            ## UI update
            self.timer_IMAP.start()
        else:
            self.set_enable_form_connect(True)
            self.label_server_log.setText("Disconnected")
            ## Thread IMAP
            self.imapServer.stop_server()
            self.timer_IMAP.stop()
            self.pushButton_server_connect.setStyleSheet("background-color: rgb(251, 251, 251)")
            self.select_server()

    def next_log_state(self):
        data = self.db.get_next_log_state(self.data_log["message_id"])
        if(data != None):
            self.data_log = data
            self.update_state_info()
            self.fill_treeWidget_log_state()

    def previous_log_state(self):
        data = self.db.get_previous_log_state(self.data_log["message_id"])
        if(data != None):
            self.data_log = data
            self.update_state_info()
            self.fill_treeWidget_log_state()

    def last_log_state(self):
        data, momsn_current = self.db.get_last_log_state(self.comboBox_state_imei.currentData())
        if(data != None):
            self.data_log = data
            self.update_state_info()
            self.fill_treeWidget_log_state()

    def update_state_imei(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.data_log, self.momsn_current = self.db.get_last_log_state(self.comboBox_state_imei.currentData())

            self.fill_treeWidget_log_state()
            self.update_momsn_bounds()
            self.update_state_info()
            self.update_tracking_seabot()

    def update_mission_info(self, row):
        self.mission_selected = row
        self.update_mission_ui()

    def update_imap(self):
        self.update_robots_list()
        self.update_state_imei()

    def update_tracking_seabot(self):
        data = self.db.get_last_pose(self.comboBox_state_imei.currentData())
        if(data!=None):
            self.layerBoat.seabot_east = data[0]
            self.layerBoat.seabot_north = data[1]

    def update_lock_view(self, val):
        self.layerBoat.enable_lock_view(val==2) # 2 = Checked

    def update_gnss_seabot_pose(self, val):
        self.layerBoat.set_enable_seabot((val==2)) # 2 = Checked

    def update_gnss_delete(self, val):
        self.layerBoat.delete_layer_exist = (val==2)

    ###########################################################################
    ## TIMERS processing

    def process_seabot(self):
        for key in self.layerSeabots:
            self.layerSeabots[key].update_pose()

    def process_boat(self):
        self.layerBoat.update()

    def process_IMAP(self):
        self.label_server_log.setText(self.imapServer.get_log())
        if(self.imapServer.get_is_connected()):
            self.pushButton_server_connect.setStyleSheet("background-color: green")
        else:
            self.pushButton_server_connect.setStyleSheet("background-color: red")

    def process_mission(self):
        if(len(self.layerMissions)>0):
            for layerMission in self.layerMissions:
                # Update mission set point on map
                layerMission.update_mission_pose()
            self.update_mission_ui()

    def update_mission_ui(self):
        if self.mission_selected != -1:
            seabotMission = self.layerMissions[self.mission_selected].get_mission()
            self.label_mission_file.setText(seabotMission.get_filename())
            # Update IHM with mission data set point
            wp = seabotMission.get_current_wp()
            # print(wp)
            if(wp!=None):
                if(wp.get_depth()==0.0 or seabotMission.is_end_mission()):
                    self.label_mission_status.setText("SURFACE")
                    self.label_mission_status.setStyleSheet("background-color: green")
                else:
                    self.label_mission_status.setText("UNDERWATER")
                    self.label_mission_status.setStyleSheet("background-color: red")

                self.label_mission_start_time.setText(str(wp.get_time_start()))
                self.label_mission_end_time.setText(str(wp.get_time_end()))
                self.label_mission_depth.setText(str(wp.get_depth()))
                self.label_mission_waypoint_id.setText(str(wp.get_id())+"/"+str(seabotMission.get_nb_wp()))
                self.label_mission_time_remain.setText(str(wp.get_time_end()-datetime.datetime.utcnow().replace(microsecond=0)))

                wp_next = seabotMission.get_next_wp()
                if(wp_next != None):
                    self.label_mission_next_depth.setText(str(wp_next.get_depth()))
                else:
                    self.label_mission_next_depth.setText("END OF MISSION")
            else:
                self.label_mission_status.setText("NO WAYPOINTS")
                self.label_mission_waypoint_id.setText(str(seabotMission.get_current_wp_id()+1) + "/"+str(seabotMission.get_nb_wp()))


            # Update Table widget
            if(self.mission_selected_last != self.mission_selected):
                wp_list = seabotMission.get_wp_list()
                self.tableWidget_mission.clearContents()
                self.tableWidget_mission.setRowCount(len(wp_list))
                row = 0
                for wp in wp_list:
                    self.tableWidget_add_waypoint(wp, row)
                    row+=1
        else:
            self.label_mission_status.setStyleSheet("background-color: gray")
            self.label_mission_start_time.setText("-")
            self.label_mission_end_time.setText("-")
            self.label_mission_depth.setText("-")
            self.label_mission_waypoint_id.setText("-")
            self.label_mission_time_remain.setText("-")
            self.label_mission_next_depth.setText("-")
            self.label_mission_status.setText("-")
            self.label_mission_waypoint_id.setText("-")
        self.mission_selected_last = self.mission_selected

    def tableWidget_add_waypoint(self, wp, row):
        time_now = datetime.datetime.utcnow().replace(microsecond=0)
        self.tableWidget_mission.setItem(row, 0, QTableWidgetItem(str(wp.get_depth())))
        self.tableWidget_mission.setItem(row, 1, QTableWidgetItem(str(wp.get_time_end()-time_now)))
        self.tableWidget_mission.setItem(row, 2, QTableWidgetItem(str(wp.get_time_start()-time_now)))
        self.tableWidget_mission.setItem(row, 3, QTableWidgetItem(str(wp.get_time_start())))
        self.tableWidget_mission.setItem(row, 4, QTableWidgetItem(str(wp.get_time_end())))
