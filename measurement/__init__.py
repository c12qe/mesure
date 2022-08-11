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

from qcodes.dataset.plotting import plot_dataset
import time


def exception_handler_general(func):
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
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"Error! What went wrong is {e}.")
    return inner_function

class MultiChannelDevice:

    @exception_handler_general
    def __init__(self, qdac_visa, dmm_visa, print_dac_overview=True):


        t = time.localtime()
        current_time = time.strftime("%H:%M:%S", t)
        # try self.qdac:
        #     print("QDAC was not closed properly - using the already open instance.")
        #     self.dac_open = True

        # except:
        # print(globals())

  
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

        time = np.abs(current-prev)/slope
        if time < 0.002:
            return 0.002
        else:
            return time




    @exception_handler_general   
    def dc_2d_gate_sweep(self, channel_number_1, channel_number_2, device_name ="test_device", database_file="test_measurements.db", max_voltage_ch1=1, min_voltage_ch1 = 0,max_voltage_ch2=1, min_voltage_ch2 = 0, 
                    number_of_steps_ch1 = 100,number_of_steps_ch2 = 10):
        int_time = self.dmm.get("NPLC") / 50 # The integration time -> time taken to perform a measurement.

        initialise_or_create_database_at(f"./qcodes_measurements/{database_file}")

        # You can only have 1 db at a time
        test_exp = load_or_create_experiment(
        experiment_name="1d_sweep",
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
        context_meas = Measurement(exp=test_exp, station=station, name='context') # create a new meaurement object using the station defined above.


        # Register the independent parameters...
        context_meas.register_parameter(channel_number_1_v_function)
        context_meas.register_parameter(channel_number_2_v_function)


        # ...then register the dependent parameters
        context_meas.register_parameter(self.dmm.volt, setpoints=(channel_number_1_v_function, 
                                                                    channel_number_1_v_function))

        # Time for periodic background database writes
        context_meas.write_period = 2

        # Define the tqdm progress bars:
        outter_bar = tqdm(range(number_of_steps_ch1), desc = f"Channel {channel_number_1} progress:",  position=0, leave=True)
        inner_bar = tqdm(range(number_of_steps_ch2), desc = f"Channel {channel_number_2} progress:", position=1, leave=True)
        
        with context_meas.run() as datasaver: # initialise measurement run
            

            for index_1, set_v_ch1 in enumerate(voltages_ch1): # for each voltage that we want to set on the qdac for channel '1'

                # Ramp the voltage up slowly using the waiting time function to ensure that the specified slope (default = 1) is not exceeded.
                duration_1 = self.qdac.ramp_voltages([channel_number_1,],[],[set_v_ch1,],self.waiting_time(set_v_ch1,voltages_ch1[index_1-1]))
                outter_bar.update(1) # update outer progress bar

                time.sleep(duration_1) # Wait some time after setting the channel '1' voltage.
                inner_bar.reset()

                for index_2, set_v_ch2 in enumerate(voltages_ch2):

                    # Slowly ramp up channel '2' from current voltage to current iteration voltage.
                    # Note: doNd was not used because it still gave a ramptime warning, using this method of the ramp_voltages to perform the sweep 
                    # eliminates the warning so we are sure that we won't accidently use too high a slope for our device.

                    duration_2 = self.qdac.ramp_voltages([channel_number_2,],[],[set_v_ch2,],self.waiting_time(set_v_ch2,voltages_ch2[index_2-1]))
                    inner_bar.update(1) 


                    time.sleep(duration_2 + 3*int_time) # wait some time including the additional integration time of our DMM.

                    get_v = self.dmm.volt.get()

                    # Save the measurement results into the db.
                    datasaver.add_result((channel_number_1_v_function, set_v_ch1),
                                            (channel_number_2_v_function, set_v_ch2),
                                            (self.dmm.volt, get_v))
                    
            # Ramp down the voltages to zero so a voltage is not left on the device.
            duration_exit = self.qdac.ramp_voltages([channel_number_1,channel_number_2],[],[0,0],self.waiting_time(0,voltages_ch2[-1])+self.waiting_time(0,voltages_ch1[-1]))
            time.sleep(duration_exit)



        # Convenient to have for plotting and data access
        dataset = datasaver.dataset

        print("Measurement complete.")
          
        return  qc.config.core.db_location # the location of the db file.


    @exception_handler_general   
    def dc_1d_gate_sweep(self, channel_number_1, channel_number_2, device_name ="test_device", database_file="test_measurements.db", fixed_voltage_ch1=0, max_voltage_ch2=1, min_voltage_ch2 = 0, 
        number_of_steps_ch2 = 100):

        int_time = self.dmm.get("NPLC") / 50 # The integration time -> time taken to perform a measurement.

        initialise_or_create_database_at(f"./qcodes_measurements/{database_file}")

        # You can only have 1 db at a time
        test_exp = load_or_create_experiment(
        experiment_name="1d_sweep",
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
        context_meas = Measurement(exp=test_exp, station=station, name='context') # create a new meaurement object using the station defined above.


        # Register the independent parameters...
        context_meas.register_parameter(channel_number_1_v_function)
        context_meas.register_parameter(channel_number_2_v_function)


        # ...then register the dependent parameters
        context_meas.register_parameter(self.dmm.volt, setpoints=(channel_number_1_v_function, 
                                                                    channel_number_1_v_function))

        # Time for periodic background database writes
        context_meas.write_period = 2

        # Define the tqdm progress bars:
        bar = tqdm(range(number_of_steps_ch2), desc = f"Channel {channel_number_2} progress:",  position=0, leave=True)
        
        with context_meas.run() as datasaver: # initialise measurement run
            


            # Ramp the voltage up slowly using the waiting time function to ensure that the specified slope (default = 1) is not exceeded.
            duration_1 = self.qdac.ramp_voltages([channel_number_1,],[],[fixed_voltage_ch1,],self.waiting_time(fixed_voltage_ch1,channel_number_1_v_function.get()))


            time.sleep(duration_1) # Wait some time after setting the channel '1' voltage.

            for index_2, set_v_ch2 in enumerate(voltages_ch2):

                # Slowly ramp up channel '2' from current voltage to current iteration voltage.
                # Note: doNd was not used because it still gave a ramptime warning, using this method of the ramp_voltages to perform the sweep 
                # eliminates the warning so we are sure that we won't accidently use too high a slope for our device.

                duration_2 = self.qdac.ramp_voltages([channel_number_2,],[],[set_v_ch2,],self.waiting_time(set_v_ch2,voltages_ch2[index_2-1]))
                bar.update(1) 


                time.sleep(duration_2 + 3*int_time) # wait some time including the additional integration time of our DMM.

                get_v = self.dmm.volt.get()

                # Save the measurement results into the db.
                datasaver.add_result((channel_number_1_v_function, fixed_voltage_ch1),
                                        (channel_number_2_v_function, set_v_ch2),
                                        (self.dmm.volt, get_v))
                    
            # Ramp down the voltages to zero so a voltage is not left on the device.
            duration_exit = self.qdac.ramp_voltages([channel_number_1,channel_number_2],[],[0,0],self.waiting_time(0,voltages_ch2[-1])+self.waiting_time(0,channel_number_1_v_function.get()))
            time.sleep(duration_exit)



        # Convenient to have for plotting and data access
        dataset = datasaver.dataset
          
        print("Measurement complete.")


        return  qc.config.core.db_location # the location of the db file.

    @exception_handler_on_close
    def close_connections(self):
        if self.dac_open:
            self.qdac.close()
            self.dac_open = False
        if self.dmm_open:
            self.dmm.close()
            self.dac_open = False
        print("Any connection to the DAC and DMM has been closed.")
        return True

    
