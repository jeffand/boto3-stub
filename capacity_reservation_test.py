# This script simulates AWS EC2 capacity reservation requests using boto3 stubs
# It demonstrates how to handle retry logic when capacity requests fail
# The script allows configuring retry attempts, delays, and number of simulated failures

import boto3
import botocore
from botocore.stub import Stubber
import time
from datetime import datetime
from botocore.exceptions import ClientError

# Centralized retry configuration
# Modify these values to adjust the retry behavior
RETRY_CONFIG = {
    'QUICK_RETRY': {
        'max_retries': 3,
        'retry_delay_seconds': 1,
        'num_failures': 3,
        'description': 'Quick retries with short delays'
    },
    'SLOW_RETRY': {
        'max_retries': 2,
        'retry_delay_seconds': 2,
        'num_failures': 2,
        'description': 'Fewer retries with longer delays'
    },
    'EXTENSIVE_RETRY': {
        'max_retries': 20,
        'retry_delay_seconds': 3,
        'num_failures': 20,
        'description': 'Many retries with longer delays'
    }
}

class CapacityReservationSimulator:
    def __init__(self, max_retries=3, retry_delay=1):
        """
        Initialize the simulator with configurable retry parameters.
        
        Args:
            max_retries (int): Maximum number of retry attempts
            retry_delay (int): Delay between retries in seconds
        """
        # Create an EC2 client - this won't actually connect to AWS since we're using stubs
        self.ec2_client = boto3.client('ec2', region_name='us-west-2')
        # Create a stubber object that will intercept API calls to AWS
        self.stubber = Stubber(self.ec2_client)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def setup_failed_response(self, error_code='InsufficientCapacity'):
        """
        Setup the stubber to return a failure response.
        This method configures what error response the stubber should return
        when create_capacity_reservation is called.
        
        Args:
            error_code (str): The AWS error code to simulate
        """
        # Create an error response that mimics AWS API error format
        error_response = {
            'Error': {
                'Code': error_code,
                'Message': f'Simulated {error_code} error'
            }
        }
        
        # Configure the stubber to return an error when create_capacity_reservation
        # is called with these specific parameters
        self.stubber.add_client_error(
            'create_capacity_reservation',  # AWS API method to stub
            service_error_code=error_code,
            service_message=f'Simulated {error_code} error',
            # Expected parameters that should match the actual API call
            expected_params={
                'InstanceType': 't2.micro',
                'InstancePlatform': 'Linux/UNIX',
                'AvailabilityZone': 'us-west-2a',
                'InstanceCount': 1
            }
        )

    def create_capacity_reservation_with_retry(self):
        """
        Attempt to create a capacity reservation with configurable retries.
        This method simulates making API calls to AWS with retry logic.
        """
        attempt = 0
        
        while attempt < self.max_retries:
            try:
                print(f"\nAttempt {attempt + 1} of {self.max_retries}")
                # Attempt to create a capacity reservation
                # Since we're using stubs, this will trigger our simulated error
                response = self.ec2_client.create_capacity_reservation(
                    InstanceType='t2.micro',
                    InstancePlatform='Linux/UNIX',
                    AvailabilityZone='us-west-2a',
                    InstanceCount=1
                )
                return response
            
            except ClientError as e:
                # Extract error details from the AWS-style error response
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                print(f"Error occurred: {error_code} - {error_message}")
                
                # If we haven't reached max retries, wait before trying again
                if attempt < self.max_retries - 1:
                    print(f"Waiting {self.retry_delay} seconds before retrying...")
                    time.sleep(self.retry_delay)
                
                attempt += 1
        
        print("\nMax retries exceeded. Capacity reservation failed.")
        return None

def run_simulation(max_retries=3, retry_delay=1, num_failures=3):
    """
    Run the capacity reservation simulation with configurable parameters.
    
    Args:
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
        num_failures (int): Number of failed responses to simulate
    """
    # Create a simulator instance with specified retry configuration
    simulator = CapacityReservationSimulator(max_retries, retry_delay)
    
    # Setup the expected number of failed responses
    # Each call to setup_failed_response adds one error response to the queue
    for _ in range(num_failures):
        simulator.setup_failed_response()
    
    # The stubber context manager ensures AWS calls are intercepted
    with simulator.stubber:
        print(f"\nStarting simulation with:")
        print(f"Max retries: {max_retries}")
        print(f"Retry delay: {retry_delay} seconds")
        print(f"Number of simulated failures: {num_failures}")
        
        simulator.create_capacity_reservation_with_retry()

if __name__ == "__main__":
    # Example usage showing different retry configurations using centralized config
    
    # Test Case 1: Quick retries configuration
    print("\nTest Case 1: Quick Retries")
    quick_config = RETRY_CONFIG['QUICK_RETRY']
    print(f"Using configuration: {quick_config['description']}")
    run_simulation(
        max_retries=quick_config['max_retries'],
        retry_delay=quick_config['retry_delay_seconds'],
        num_failures=quick_config['num_failures']
    )
    
    # Test Case 2: Slow retries configuration
    print("\nTest Case 2: Slow Retries")
    slow_config = RETRY_CONFIG['SLOW_RETRY']
    print(f"Using configuration: {slow_config['description']}")
    run_simulation(
        max_retries=slow_config['max_retries'],
        retry_delay=slow_config['retry_delay_seconds'],
        num_failures=slow_config['num_failures']
    )
    
    # Test Case 3: Extensive retries configuration
    print("\nTest Case 3: Extensive Retries")
    extensive_config = RETRY_CONFIG['EXTENSIVE_RETRY']
    print(f"Using configuration: {extensive_config['description']}")
    run_simulation(
        max_retries=extensive_config['max_retries'],
        retry_delay=extensive_config['retry_delay_seconds'],
        num_failures=extensive_config['num_failures']
    )
