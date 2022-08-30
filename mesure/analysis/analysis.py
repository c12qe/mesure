from cProfile import label
import qcodes as qc
from qcodes.dataset import (
    Measurement,
    experiments,
    initialise_or_create_database_at,
    load_by_run_spec,
    load_or_create_experiment,
)
import numpy as np
import matplotlib.pyplot as plt
from qcodes.dataset.plotting import plot_dataset


class Analyser:
    """Class to create object to analyse a specific database of measurements

    Args:
         database_file (str): the database file of the measurments that you want to analyses. Defaults to "test".

    """

    def __init__(self, database_file="test"):
        """Function to initialise instance of class and output the experiments contained inside the data file."""

        # analyser
        #     experiments
        #         datasets_in_experiments

        # initialise database to find the experiments.
        initialise_or_create_database_at(f"./measurement_results/{database_file}")
        print("The experiments found in", database_file,"are:")
        print(experiments())




    def datasets_in_experiments(self, experiment_name ="test_device", device_name="test_device"):
        """Function to output the different datasets contained inside a given experiment.

        Args:
            experiment_name (str): The experiment from which you wish to select your dataset. Defaults to "test_device".
            device_name (str): The device upon which your experiment was conducted. Defaults to "test_device".
        
        Returns:
            bool: True if completed successfully.
        """
        exp = load_or_create_experiment(
            experiment_name=experiment_name,
            sample_name=device_name
        )
        print(f"The datasets collected for the '{experiment_name}' experiment are:")
        print(exp.data_sets())
    
    def display_experiment_dataset(self, experiment_name ="test_device", run_id=1):
        """Function to visualise a given run id for an experiment found in the database specified in the object definition.

        Args:
            experiment_name (str): The experiment from which you wish to select your dataset. Defaults to "test_device". 
            run_id (int): The run id you want to visualise. Defaults to 1.
        
        """
        dataset = load_by_run_spec(experiment_name=experiment_name, captured_run_id=run_id)
        df = dataset.to_pandas_dataframe()

        return df

      
          
    def plot_channel_sweep(self, channels=[], experiment_name="test_device", run_id=1):
        """Function to visualise a sweep for a given run id for an experiment found in the database specified in the object definition.

        Args:
            channels (list): The channels you want to visualise. Defaults to [].
            experiment_name (str): The experiment from which you wish to select your dataset. Defaults to "test_device". 
            run_id (int): The run id you want to visualise. Defaults to 1.
        
        """
        
        assert  (len(channels) == 2) or (len(channels) == 1), "Make sure you're only trying to plot for two or one gate."
        dataset = load_by_run_spec(experiment_name=experiment_name, captured_run_id=run_id)
        df = dataset.to_pandas_dataframe()
        x = df.index.get_level_values("qdac_chan{:02d}_v".format(channels[0])).values
        z = df["DMM_volt"]    

        fig1, ax1 = plt.subplots(constrained_layout=True)
        gain = 10**7
        if len(channels) == 2:

            # pre-processing of data for plotting
            y = df.index.get_level_values("qdac_chan{:02d}_v".format(channels[1])).values
            x_unique = np.unique(x, return_counts=True)
            x_unique_values = x_unique[0]
            x_unique_n = len(x_unique[1])

            y_unique = np.unique(y, return_counts=True)
            y_unique_values = y_unique[0]
            y_unique_n = len(y_unique[1])

            z = z.to_numpy() / gain
            z= np.abs(z.reshape((x_unique_n, y_unique_n)))

            # plot data and set labels
            CS = ax1.contourf(x_unique_values,y_unique_values,z, levels=1000)
            # ax1.set_title(f'2D Sweep of Channels {channels[0]} and {channels[1]}')
            ax1.set_xlabel(f'Channel {channels[0]} (V)')
            ax1.set_ylabel(f'Channel {channels[1]} (V)')
            # ax1.set_yticks([0, 0.1, 0.2, 0.3, 0.4])

            # labels = [-1.50,-0.75,0.00,0.75,1.50]
            # ax1.set_yticklabels(labels)
            cbar = fig1.colorbar(CS)
            cbar.set_label("I (A)")


        else:
            # ax1.set_title(f'1D Sweep of Channel {channels[0]}')
            ax1.set_xlabel(f'Channel {channels[0]} (V)')
            ax1.set_ylabel('I (A)')
            ax1.plot(x,z)
        
        
        plt.show()
            


        
       