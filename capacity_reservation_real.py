# This script creates EC2 capacity reservations using real AWS API calls
# It implements retry logic for handling InsufficientCapacity errors
# The script includes proper error handling, logging, and cleanup functionality

import boto3
import time
import logging
from botocore.exceptions import ClientError

# Set up logging configuration to track all operations and errors
# The format includes timestamp, log level, and message for detailed tracking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Centralized retry configuration - matches test version for consistency
# Each configuration specifies:
# - max_retries: maximum number of attempts to make
# - retry_delay_seconds: time to wait between attempts
# - description: human-readable explanation of the configuration
RETRY_CONFIG = {
    'QUICK_RETRY': {
        'max_retries': 3,
        'retry_delay_seconds': 1,
        'description': 'Quick retries with short delays'
    },
    'SLOW_RETRY': {
        'max_retries': 2,
        'retry_delay_seconds': 2,
        'description': 'Fewer retries with longer delays'
    },
    'EXTENSIVE_RETRY': {
        'max_retries': 20,
        'retry_delay_seconds': 3,
        'description': 'Many retries with longer delays'
    }
}

class CapacityReservationManager:
    def __init__(self, region_name='us-west-2', retry_config='QUICK_RETRY'):
        """
        Initialize the Capacity Reservation Manager with AWS credentials and retry configuration.
        
        Args:
            region_name (str): AWS region name
            retry_config (str): Key from RETRY_CONFIG dictionary
        """
        # Create a real AWS EC2 client - requires proper AWS credentials
        self.ec2_client = boto3.client('ec2', region_name=region_name)
        # Load the specified retry configuration
        self.config = RETRY_CONFIG[retry_config]
        self.max_retries = self.config['max_retries']
        self.retry_delay = self.config['retry_delay_seconds']
        logger.info(f"Initialized with {self.config['description']}")

    def create_capacity_reservation(self, instance_type, instance_count, 
                                 availability_zone, platform='Linux/UNIX'):
        """
        Create an EC2 capacity reservation with retry logic for InsufficientCapacity errors.
        
        Args:
            instance_type (str): EC2 instance type (e.g., 't2.micro')
            instance_count (int): Number of instances to reserve
            availability_zone (str): AWS availability zone
            platform (str): Operating system platform
        
        Returns:
            dict: Reservation details if successful, None if all retries failed
        """
        attempt = 0
        
        while attempt < self.max_retries:
            try:
                logger.info(f"\nAttempt {attempt + 1} of {self.max_retries}")
                
                # Make the actual AWS API call to create a capacity reservation
                # This will fail with InsufficientCapacity if AWS cannot fulfill the request
                response = self.ec2_client.create_capacity_reservation(
                    InstanceType=instance_type,
                    InstancePlatform=platform,
                    AvailabilityZone=availability_zone,
                    InstanceCount=instance_count,
                    EndDateType='unlimited'  # Reservation doesn't expire automatically
                )
                
                # Extract and log the reservation ID on successful creation
                reservation_id = response['CapacityReservation']['CapacityReservationId']
                logger.info(f"Successfully created capacity reservation: {reservation_id}")
                return response['CapacityReservation']
                
            except ClientError as e:
                # Extract error details from the AWS error response
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                
                if error_code == 'InsufficientCapacity':
                    # Handle capacity-specific errors with retry logic
                    logger.warning(f"Insufficient capacity error: {error_message}")
                    
                    if attempt < self.max_retries - 1:
                        logger.info(f"Waiting {self.retry_delay} seconds before retrying...")
                        time.sleep(self.retry_delay)
                    
                    attempt += 1
                else:
                    # For non-capacity errors (e.g., permissions, invalid parameters)
                    # log the error and raise immediately - no retry
                    logger.error(f"AWS Error: {error_code} - {error_message}")
                    raise
        
        logger.error("Max retries exceeded. Failed to create capacity reservation.")
        return None

    def cleanup_reservation(self, reservation_id):
        """
        Clean up a capacity reservation by canceling it.
        This prevents unnecessary costs for unused reservations.
        
        Args:
            reservation_id (str): The ID of the capacity reservation to cancel
        """
        try:
            # Make AWS API call to cancel the reservation
            self.ec2_client.cancel_capacity_reservation(
                CapacityReservationId=reservation_id
            )
            logger.info(f"Successfully canceled reservation: {reservation_id}")
        except ClientError as e:
            logger.error(f"Error canceling reservation: {e}")
            raise

def main():
    # Example usage of the CapacityReservationManager
    # Uses the extensive retry configuration for maximum attempts
    manager = CapacityReservationManager(retry_config='EXTENSIVE_RETRY')
    
    try:
        # Attempt to create a capacity reservation with specific parameters
        reservation = manager.create_capacity_reservation(
            instance_type='t2.micro',
            instance_count=1,
            availability_zone='us-west-2a'
        )
        
        if reservation:
            # Log all the details of the successful reservation
            logger.info("Reservation details:")
            logger.info(f"Reservation ID: {reservation['CapacityReservationId']}")
            logger.info(f"Instance Type: {reservation['InstanceType']}")
            logger.info(f"Instance Count: {reservation['InstanceCount']}")
            logger.info(f"Availability Zone: {reservation['AvailabilityZone']}")
            
            # Clean up the reservation to avoid unnecessary costs
            manager.cleanup_reservation(reservation['CapacityReservationId'])
    
    except ClientError as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()
