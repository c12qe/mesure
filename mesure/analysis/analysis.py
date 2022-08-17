import qcodes as qc
from qcodes.dataset import (
    Measurement,
    experiments,
    initialise_or_create_database_at,
    load_by_run_spec,
    load_or_create_experiment,
)

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
        print(f"The data collected for run {run_id} experiment is shown below:")

        print(df.head())
        plot_dataset(dataset)

      
          



    
