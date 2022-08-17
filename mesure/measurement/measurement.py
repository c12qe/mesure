from logging import exception
import pyvisa as visa
import numpy as np
import matplotlib.pyplot as plt
import qcodes as qc
from qcodes.dataset import (
    Measurement,
    experiments,
    initialise_or_create_database_at,
    load_by_run_spec,
    load_or_create_experiment,
)
from tqdm.notebook import tqdm

from qcodes.instrument_drivers.QDevil.QDevil_QDAC import *
from qcodes.instrument_drivers.Keysight.Keysight_34410A_submodules import *

import time


def exception_handler_general(func):
    
    """Decorator function to handle general case exceptions, so that
       no instrument remains open in the case of an error, KeyboardInterrupt or SystemExit.

    Args:
        func: A callable function.

   Returns:
        bool: The return of func if successful. False if unsuccessful.
    """
    def inner_function(*args, **kwargs):
        self_arg = args[0] # First argument is the self
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"Error! What went wrong is {e}.")
            self_arg.close_connections()


        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            self_arg.close_connections()

        except SystemExit:
            print("SystemExit")


            self_arg.close_connections()

    return inner_function


def exception_handler_on_close(func):
    """Decorator function to handle exceptions that occur when closing the connection to the measurement instruments.

    Args:
        func: A callable function.
   
    Returns:
        bool: The return of func if successful. False if unsuccessful.
    """
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"Error! What went wrong is {e}.")
    return inner_function

class Device:
    """Class to create multichannel device object for measurement sweeps.

    Args:
            qdac_visa (string): the visa address of the QDAC.
            dmm_visa (string): the visa a
            print_dac_overview (bool): Whether to print an overview of the DAC channels. Defaults to True.
    """

    @exception_handler_general
    def __init__(self, qdac_visa, dmm_visa, print_dac_overview=True, connected_channels=[], investigation_channels=[]):
        """Function to initialise instance of class. """

        t = time.localtime()
        current_time = time.strftime("%H:%M:%S", t)
        self.connected_channels=connected_channels
        self.investigation_channels=investigation_channels

        self.qdac = QDac(name = 'qdac', address= qdac_visa, update_currents=False)
        self.dac_open = True

        print(f"Connected to QDAC on {qdac_visa} at {current_time}.")
        self.dmm = Keysight_34410A('DMM', address=dmm_visa)
        self.dmm_open = True

        self.qdac.reset()

        for i in range(1,25):
            # Set mode of the channels
            eval("self.qdac.ch{:02d}.mode".format(i))(Mode.vhigh_ilow)

            # Set slope of channels to 1 V/s
            eval("self.qdac.ch{:02d}.slope".format(i))(1)

        if print_dac_overview:
            print("\nOverview of QDAC channels:\n")
            print(self.qdac.print_overview(update_currents=True))

    def waiting_time(self, current,prev, slope=1):   
        """The ramptime to use betweem the ramping between two voltages.

        Args:
            current (float): the current voltage that you want to update to.
            prev (float):the previous voltage that you want to update from
            slope (float): the rate of voltage change in V/s. Defaults to 1.

        Returns:
            float: the ramptime to use for ramping the voltage on a channel.
        """

        time = np.abs(current-prev)/slope
        if time < 0.002:
            return 0.002
        else:
            return time

    @exception_handler_general
    def set_channel_voltage(self,channel_number, voltage_value=0.0):
        channel_number_abrev = "self.qdac.ch" + str(channel_number) + ".v"
        channel_number_v_function = eval(channel_number_abrev)

        duration = self.qdac.ramp_voltages([channel_number,],[],[voltage_value,],self.waiting_time(voltage_value,channel_number_v_function.get()))
        time.sleep(duration) # Wait some time after setting the channel voltage.
        return True

    @exception_handler_general
    def get_channel_voltage(self,channel_number):
        channel_number_abrev = "self.qdac.ch" + str(channel_number) + ".v"
        channel_number_v_function = eval(channel_number_abrev)
        return channel_number_v_function.get()

    @exception_handler_general
    def get_current(self):
        # Need to see how we actually measure current first. Add VNA functionality too.
        return self.dmm.volt.get()
    



    @exception_handler_general   
    def dc_2d_gate_sweep(self, channel_number_1, channel_number_2, experiment_name="test", device_name ="test_device", database_file="test_measurements.db", max_voltage_ch1=1, min_voltage_ch1 = 0,max_voltage_ch2=1, min_voltage_ch2 = 0, 
                    number_of_steps_ch1 = 100,number_of_steps_ch2 = 100):
        """Function to perform a measurement sweep of 2 gates on the device.

        Args:
            channel_number_1 (int): The channel number associated with the 1st channel.
            channel_number_2 (int): The channel number associated with the 2nd channel.
            experiment_name (str): The name of the experiment which tp associate this measurment with. Defaults to "test".
            device_name (str): The name of your device. Defaults to "test_device".
            database_file (str): The name of the database file to which you want to save your results. Defaults to "test_measurements.db".
            max_voltage_ch1 (float): The maximum voltage to sweep your 1st channel to. Defaults to 1.
            min_voltage_ch1 (float): The minimum voltage to sweep your 1st channel to. Defaults to 0.
            max_voltage_ch2 (float): The maximum voltage to sweep your 2nd channel to. Defaults to 1.
            min_voltage_ch2 (float): The minimum voltage to sweep your 2nd channel from. Defaults to 0.
            number_of_steps_ch1 (int): The number of measurement steps to use during the voltage sweep for the 1st channel. Defaults to 100.
            number_of_steps_ch2 (int):  The number of measurement steps to use during the voltage sweep for the 2nd channel. Defaults to 100.

        Returns:
            str: The local path to the database file to which the measurement was saved.
        """
        int_time = self.dmm.get("NPLC") / 50 # The integration time -> time taken to perform a measurement.

        initialise_or_create_database_at(f"./measurement_results/{database_file}")

        # You can only have 1 db at a time
        test_exp = load_or_create_experiment(
        experiment_name=experiment_name,
        sample_name=device_name)

        # Perform concatination and use eval to store the .v methods for the channel numbers passed as arugments
        channel_number_1_abrev = "self.qdac.ch" + str(channel_number_1) + ".v"
        channel_number_2_abrev = "self.qdac.ch" + str(channel_number_2) + ".v"
        channel_number_1_v_function = eval(channel_number_1_abrev)
        channel_number_2_v_function = eval(channel_number_2_abrev)


        voltages_ch1 = np.linspace(min_voltage_ch1, max_voltage_ch1, number_of_steps_ch1) # create a numpy array with all the voltages to be set on each channel
        voltages_ch2 = np.linspace(min_voltage_ch2, max_voltage_ch2, number_of_steps_ch2)
        
        # produce a station object to store the instruments to be used during the experiment
        station = qc.Station()

        station.add_component(self.qdac)
        station.add_component(self.dmm)

        # The Measurement object is used to obtain data from instruments in QCoDeS, 
        # It is instantiated with both an experiment (to handle data) and station to control the instruments.
        context_meas = Measurement(exp=test_exp, station=station, name='2d_sweep') # create a new meaurement object using the station defined above.


        # Register the independent parameters...
        context_meas.register_parameter(channel_number_1_v_function)
        context_meas.register_parameter(channel_number_2_v_function)


        # ...then register the dependent parameters
        context_meas.register_parameter(self.dmm.volt, setpoints=(channel_number_1_v_function, 
                                                                    channel_number_2_v_function))

        # Time for periodic background database writes
        context_meas.write_period = 2

        # Define the tqdm progress bars:
        outter_bar = tqdm(range(number_of_steps_ch1), desc = f"Channel {channel_number_1} progress:",  position=0, leave=True)
        inner_bar = tqdm(range(number_of_steps_ch2), desc = f"Channel {channel_number_2} progress:", position=1, leave=True)
        
        with context_meas.run() as datasaver: # initialise measurement run 

            for set_v_ch1 in voltages_ch1: # for each voltage that we want to set on the qdac for channel '1'

                # Ramp the voltage up slowly using the waiting time function to ensure that the specified slope (default = 1) is not exceeded.
                self.set_channel_voltage(channel_number_1, set_v_ch1)
                outter_bar.update(1) # update outer progress bar

                inner_bar.reset()

                for set_v_ch2 in voltages_ch2:

                    # Slowly ramp up channel '2' from current voltage to current iteration voltage.
                    # Note: doNd was not used because it still gave a ramptime warning, using this method of the ramp_voltages to perform the sweep 
                    # eliminates the warning so we are sure that we won't accidently use too high a slope for our device.
                    self.set_channel_voltage(channel_number_2, set_v_ch2)

                    inner_bar.update(1) 
                    time.sleep(3*int_time) # wait some time including the additional integration time of our DMM.

                    get_v = self.dmm.volt.get()

                    # Save the measurement results into the db.
                    datasaver.add_result((channel_number_1_v_function, set_v_ch1),
                                            (channel_number_2_v_function, set_v_ch2),
                                            (self.dmm.volt, get_v))
                    
            
            print("Measurement complete.")

            # Ramp down the voltages to zero so a voltage is not left on the device.
            for channel_num in range(1,25):
                self.set_channel_voltage(channel_num, 0.0)


        # # Convenient to have for plotting and data access
        # dataset = datasaver.dataset

          
        return  qc.config.core.db_location # the location of the db file.

    @exception_handler_general   
    def dc_1d_gate_sweep(self, channel_number_1, channel_number_2, experiment_name="test", device_name ="test_device", database_file="test_measurements.db", fixed_voltage_ch1=0, max_voltage_ch2=1, min_voltage_ch2 = 0, 
        number_of_steps_ch2 = 100):
        """Function to perform a measurement sweep of 1 of the gates on the device, whilst keeping the others fixed.

        Args:
            channel_number_1 (int): The channel number associated with the 1st channel.
            channel_number_2 (int): The channel number associated with the 2nd channel.
            experiment_name (str): The name of the experiment which tp associate this measurment with. Defaults to "test".
            device_name (str): The name of your device. Defaults to "test_device".
            database_file (str): The name of the database file to which you want to save your results. Defaults to "test_measurements.db".
            fixed_voltage_ch1 (float): The fixed voltage to use for the 1st channel.
            max_voltage_ch2 (float): The maximum voltage to sweep your 2nd channel to. Defaults to 1.
            min_voltage_ch2 (float): The minimum voltage to sweep your 2nd channel from. Defaults to 0.
            number_of_steps_ch2 (int):  The number of measurement steps to use during the voltage sweep for the 2nd channel. Defaults to 100.

        Returns:
            str: The local path to the database file to which the measurement was saved.
        """

        int_time = self.dmm.get("NPLC") / 50 # The integration time -> time taken to perform a measurement.

        initialise_or_create_database_at(f"./measurement_results/{database_file}")

        # You can only have 1 db at a time
        test_exp = load_or_create_experiment(
        experiment_name=experiment_name,
        sample_name=device_name)

        # Perform concatination and use eval to store the .v methods for the channel numbers passed as arugments
        channel_number_1_abrev = "self.qdac.ch" + str(channel_number_1) + ".v"
        channel_number_2_abrev = "self.qdac.ch" + str(channel_number_2) + ".v"
        channel_number_1_v_function = eval(channel_number_1_abrev)
        channel_number_2_v_function = eval(channel_number_2_abrev)

        # create a numpy array with all the voltages to be set on channel 2
        voltages_ch2 = np.linspace(min_voltage_ch2, max_voltage_ch2, number_of_steps_ch2)
        
        # produce a station object to store the instruments to be used during the experiment
        station = qc.Station()

        station.add_component(self.qdac)
        station.add_component(self.dmm)

        # The Measurement object is used to obtain data from instruments in QCoDeS, 
        # It is instantiated with both an experiment (to handle data) and station to control the instruments.
        context_meas = Measurement(exp=test_exp, station=station, name='1d_sweep') # create a new meaurement object using the station defined above.

        # Register the independent parameters...
        context_meas.register_parameter(channel_number_1_v_function)
        context_meas.register_parameter(channel_number_2_v_function)

        # ...then register the dependent parameters
        context_meas.register_parameter(self.dmm.volt, setpoints=(channel_number_1_v_function, 
                                                                    channel_number_2_v_function))

        # Time for periodic background database writes
        context_meas.write_period = 2

        # Define the tqdm progress bars:
        bar = tqdm(range(number_of_steps_ch2), desc = f"Channel {channel_number_2} progress:",  position=0, leave=True)
        
        with context_meas.run() as datasaver: # initialise measurement run
            
            # Ramp the voltage up slowly using the waiting time function to ensure that the specified slope (default = 1) is not exceeded.
            self.set_channel_voltage(channel_number_1, fixed_voltage_ch1)

            for set_v_ch2 in voltages_ch2:

                # Slowly ramp up channel '2' from current voltage to current iteration voltage.
                # Note: doNd was not used because it still gave a ramptime warning, using this method of the ramp_voltages to perform the sweep 
                # eliminates the warning so we are sure that we won't accidently use too high a slope for our device.

                self.set_channel_voltage(channel_number_1, set_v_ch2)
                bar.update(1) 

                time.sleep(3*int_time) # wait some time including the additional integration time of our DMM.

                get_v = self.dmm.volt.get()

                # Save the measurement results into the db.
                datasaver.add_result((channel_number_1_v_function, fixed_voltage_ch1),
                                        (channel_number_2_v_function, set_v_ch2),
                                        (self.dmm.volt, get_v))
                    
            # Ramp down the voltages to zero so a voltage is not left on the device.
            for channel_num in range(1,25):
                self.set_channel_voltage(channel_num, 0.0)
                
        # # Convenient to have for plotting and data access
        # dataset = datasaver.dataset
          
        print("Measurement complete.")

        return  qc.config.core.db_location # the location of the db file.


    def jump (self, params,inv=False):
        """_summary_

        Args:
            params (list): The voltages to set on your channels.
            inv (bool): Should the investigation gates (typically plunger gates) should be used. Defaults to False.

        Returns:
            list: The params the channels were set to.
        """
        if inv:
            labels = self.investigation_channels #plunger gates
        else:
            labels = self.connected_channels #all gates
            
        assert len(params) == len(labels) #params needs to be the same length as labels
        for i in range(len(params)):
            self.set_channel_voltage(labels[i],params[i]) #function that takes dac key and value and sets dac to that value
        return params

    def check(self, inv=True):
        
        if inv:
            labels = self.investigation_channels #plunger gates
        else:
            labels =self.connected_channels #all gates
        dac_state = [None]*len(labels)
        for i in range(len(labels)):
            dac_state[i] = self.get_channel_voltage(labels[i]) #function that takes dac key and returns state that channel is in
        return dac_state

    def measure(self):
        current = self.get_current() #receive a single current measurement from the daq
        return current
    

    @exception_handler_on_close
    def close_connections(self):
        """Function to close the connections to the connected measurment equipment.

        Returns:
            bool: True if connnections successfully closed.
        """
        if self.dac_open:
            self.qdac.close()
            self.dac_open = False
        if self.dmm_open:
            self.dmm.close()
            self.dac_open = False
        print("Any connection to the DAC and DMM has been closed.")
        return True

    
