#!/usr/bin/env python3

import argparse
import boto3
import time
import logging
import json
import inquirer
from botocore.stub import Stubber
from botocore.exceptions import ClientError
from datetime import datetime
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common instance types by use case
INSTANCE_TYPE_CHOICES = {
    'general_purpose': ['t2.micro', 't3.micro', 't3.small', 'm5.large'],
    'compute_optimized': ['c5.large', 'c5.xlarge', 'c5.2xlarge'],
    'memory_optimized': ['r5.large', 'r5.xlarge', 'r5.2xlarge'],
    'storage_optimized': ['i3.large', 'i3.xlarge'],
    'gpu': ['g4dn.xlarge', 'p3.2xlarge']
}

# Platform choices
PLATFORM_CHOICES = [
    'Linux/UNIX',
    'Red Hat Enterprise Linux',
    'SUSE Linux',
    'Windows',
    'Windows with SQL Server',
    'Windows with SQL Server Enterprise',
    'Windows with SQL Server Standard',
    'Windows with SQL Server Web'
]

# Region and AZ choices (common ones)
REGION_CHOICES = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-central-1', 'ap-southeast-1', 'ap-northeast-1'
]

# Retry configurations
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

def get_interactive_choices():
    """Walk through all parameters interactively"""
    from datetime import datetime, timezone as tz
    
    questions = [
        # Instance Type Selection (two-step process)
        inquirer.List('instance_category',
                     message="Select instance type category",
                     choices=list(INSTANCE_TYPE_CHOICES.keys()),
                     default='general_purpose'),
        
        # Instance Count
        inquirer.Text('instance_count',
                     message="Enter number of instances to reserve",
                     default='1',
                     validate=lambda _, x: x.isdigit() and int(x) > 0),
        
        # Platform Selection
        inquirer.List('platform',
                     message="Select instance platform",
                     choices=PLATFORM_CHOICES,
                     default='Linux/UNIX'),
        
        # Region Selection
        inquirer.List('region',
                     message="Select AWS region",
                     choices=REGION_CHOICES,
                     default='us-west-2'),
        
        # Availability Zone Selection (will be populated after region selection)
        inquirer.Text('availability_zone',
                     message="Enter availability zone (leave empty for first AZ in region)",
                     default=''),
        
        # EBS Optimization
        inquirer.Confirm('ebs_optimized',
                        message="Enable EBS optimization?",
                        default=False),
        
        # Tenancy
        inquirer.List('tenancy',
                     message="Select instance tenancy",
                     choices=['default', 'dedicated'],
                     default='default'),
        
        # End Date Configuration
        inquirer.List('end_date_type',
                     message="Select reservation end date type",
                     choices=['unlimited', 'limited'],
                     default='unlimited'),
        
        # Retry Configuration
        inquirer.List('retry_config',
                     message="Select retry configuration",
                     choices=[f"{k} ({v['description']})" for k, v in RETRY_CONFIG.items()],
                     default='QUICK_RETRY (Quick retries with short delays)'),
        
        # Custom Retry Options
        inquirer.Text('custom_max_retries',
                     message="Enter custom max retries (0 to use retry config value)",
                     default='0',
                     validate=lambda _, x: x.isdigit()),
        
        inquirer.Text('custom_retry_delay',
                     message="Enter custom retry delay in seconds (0 to use retry config value)",
                     default='0',
                     validate=lambda _, x: x.isdigit()),
        
        inquirer.Text('max_wait_time',
                     message="Enter maximum total wait time in seconds",
                     default='3600',
                     validate=lambda _, x: x.isdigit() and int(x) > 0),
        
        # Execution Mode
        inquirer.Confirm('simulation_mode',
                        message="Run in simulation mode?",
                        default=True),
        
        # Log Level
        inquirer.List('log_level',
                     message="Select logging level",
                     choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                     default='INFO'),
        
        # Cleanup Configuration
        inquirer.Confirm('cleanup_on_failure',
                        message="Clean up failed reservations?",
                        default=True)
    ]
    
    answers = inquirer.prompt(questions)
    
    # Handle instance type selection as second step
    instance_category = answers.pop('instance_category')
    instance_type_question = [
        inquirer.List('instance_type',
                     message="Select specific instance type",
                     choices=INSTANCE_TYPE_CHOICES[instance_category],
                     default=INSTANCE_TYPE_CHOICES[instance_category][0])
    ]
    instance_type_answer = inquirer.prompt(instance_type_question)
    answers.update(instance_type_answer)
    
    # Handle end date if limited was selected
    if answers['end_date_type'] == 'limited':
        end_date_question = [
            inquirer.Text('end_date',
                         message="Enter end date (ISO 8601 format, e.g., 2024-12-31T23:59:59)",
                         validate=lambda _, x: len(x) > 0)
        ]
        end_date_answer = inquirer.prompt(end_date_question)
        # Convert end_date string to timezone-aware datetime
        end_date = datetime.fromisoformat(end_date_answer['end_date'])
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=tz.utc)
        answers['end_date'] = end_date.isoformat()
    else:
        answers['end_date'] = None
    
    # Handle tags
    tags_question = [
        inquirer.Confirm('add_tags',
                        message="Would you like to add tags?",
                        default=False)
    ]
    tags_answer = inquirer.prompt(tags_question)
    
    if tags_answer['add_tags']:
        tags = {}
        while True:
            tag_questions = [
                inquirer.Text('key',
                            message="Enter tag key",
                            validate=lambda _, x: len(x) > 0),
                inquirer.Text('value',
                            message="Enter tag value",
                            validate=lambda _, x: len(x) > 0),
                inquirer.Confirm('add_another',
                               message="Add another tag?",
                               default=False)
            ]
            tag_answers = inquirer.prompt(tag_questions)
            tags[tag_answers['key']] = tag_answers['value']
            if not tag_answers['add_another']:
                break
        
        answers['tags'] = tags
    else:
        answers['tags'] = {}
    
    # Clean up retry config selection to match expected format
    answers['retry_config'] = answers['retry_config'].split(' ')[0]
    
    # Convert numeric values
    answers['instance_count'] = int(answers['instance_count'])
    answers['custom_max_retries'] = int(answers['custom_max_retries'])
    answers['custom_retry_delay'] = int(answers['custom_retry_delay'])
    answers['max_wait_time'] = int(answers['max_wait_time'])
    
    # Handle empty availability zone
    if not answers['availability_zone']:
        answers['availability_zone'] = f"{answers['region']}a"
    
    return answers

def parse_args():
    parser = argparse.ArgumentParser(
        description='AWS EC2 Capacity Reservation CLI with simulation capabilities'
    )
    
    parser.add_argument('--non-interactive',
                       action='store_true',
                       help='Run in non-interactive mode with command line arguments')
    
    # Only parse other arguments if --non-interactive is specified
    args, remaining = parser.parse_known_args()
    
    if args.non_interactive:
        # Instance Configuration
        instance_group = parser.add_argument_group('Instance Configuration')
        instance_group.add_argument('--instance-type', 
                                  default='t2.micro',
                                  choices=[inst for types in INSTANCE_TYPE_CHOICES.values() for inst in types],
                                  help='EC2 instance type')
        instance_group.add_argument('--instance-count', 
                                  type=int,
                                  default=1,
                                  help='Number of instances to reserve')
        instance_group.add_argument('--platform',
                                  default='Linux/UNIX',
                                  choices=PLATFORM_CHOICES,
                                  help='Operating system platform')
        
        # Location Configuration
        location_group = parser.add_argument_group('Location Configuration')
        location_group.add_argument('--region',
                                  default='us-west-2',
                                  choices=REGION_CHOICES,
                                  help='AWS region')
        location_group.add_argument('--availability-zone',
                                  help='Availability zone (default: first AZ in region)')
        
        # Reservation Configuration
        reservation_group = parser.add_argument_group('Reservation Configuration')
        reservation_group.add_argument('--ebs-optimized',
                                     action='store_true',
                                     help='Enable EBS optimization')
        reservation_group.add_argument('--tenancy',
                                     choices=['default', 'dedicated'],
                                     default='default',
                                     help='Instance tenancy')
        reservation_group.add_argument('--end-date-type',
                                     choices=['unlimited', 'limited'],
                                     default='unlimited',
                                     help='Reservation end date type')
        reservation_group.add_argument('--end-date',
                                     help='End date for limited reservations (ISO 8601 format)')
        reservation_group.add_argument('--tags',
                                     type=json.loads,
                                     default='{}',
                                     help='Tags in JSON format (e.g., \'{"Key": "Value"}\')')
        
        # Retry Configuration
        retry_group = parser.add_argument_group('Retry Configuration')
        retry_group.add_argument('--retry-config',
                               choices=list(RETRY_CONFIG.keys()),
                               default='QUICK_RETRY',
                               help='Predefined retry configuration')
        retry_group.add_argument('--custom-max-retries',
                               type=int,
                               default=0,
                               help='Override max retries (0 to use retry config value)')
        retry_group.add_argument('--custom-retry-delay',
                               type=int,
                               default=0,
                               help='Override retry delay in seconds (0 to use retry config value)')
        retry_group.add_argument('--max-wait-time',
                               type=int,
                               default=3600,
                               help='Maximum total wait time in seconds')
        
        # Execution Configuration
        exec_group = parser.add_argument_group('Execution Configuration')
        exec_group.add_argument('--simulation-mode',
                              action='store_true',
                              help='Run in simulation mode')
        exec_group.add_argument('--log-level',
                              choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                              default='INFO',
                              help='Logging level')
        exec_group.add_argument('--cleanup-on-failure',
                              action='store_true',
                              help='Clean up failed reservations')
        
        return parser.parse_args()
    else:
        return get_interactive_choices()

class CapacityReservationManager:
    def __init__(self, args):
        """Initialize with CLI arguments"""
        # Convert dictionary to namespace if needed
        if isinstance(args, dict):
            from types import SimpleNamespace
            args_dict = args.copy()  # Make a copy to avoid modifying the original
            # Ensure all required attributes exist
            if 'availability_zone' not in args_dict:
                args_dict['availability_zone'] = f"{args_dict['region']}a"
            if 'end_date' not in args_dict:
                args_dict['end_date'] = None
            self.args = SimpleNamespace(**args_dict)
        else:
            self.args = args

        self.ec2_client = boto3.client('ec2', region_name=self.args.region)
        
        # Configure logging
        logging.getLogger().setLevel(getattr(logging, self.args.log_level))
        
        # Set retry configuration
        self.config = RETRY_CONFIG[self.args.retry_config]
        self.max_retries = getattr(self.args, 'custom_max_retries', 0) or self.config['max_retries']
        self.retry_delay = getattr(self.args, 'custom_retry_delay', 0) or self.config['retry_delay_seconds']
        self.max_wait_time = getattr(self.args, 'max_wait_time', 3600)
        
        if self.args.simulation_mode:
            self.stubber = Stubber(self.ec2_client)
            logger.info("Running in simulation mode")
            self.setup_simulation()
        
        logger.info(f"Initialized with {self.config['description']}")
        
    def setup_simulation(self):
        """Setup simulation responses for create_capacity_reservation"""
        from datetime import datetime
        import pytz

        # Define expected parameters for the API call
        expected_params = {
            'InstanceType': self.args.instance_type,
            'InstancePlatform': self.args.platform,
            'AvailabilityZone': self.args.availability_zone,
            'Tenancy': self.args.tenancy,
            'InstanceCount': self.args.instance_count,
            'EbsOptimized': self.args.ebs_optimized,
            'EndDateType': self.args.end_date_type,
            'TagSpecifications': [{
                'ResourceType': 'capacity-reservation',
                'Tags': [{'Key': k, 'Value': v} for k, v in self.args.tags.items()]
            }] if self.args.tags else []
        }

        # Add EndDate only if it's a limited reservation
        if self.args.end_date_type == 'limited' and self.args.end_date:
            expected_params['EndDate'] = self.args.end_date

        # Get current UTC time
        current_time = datetime.now(pytz.UTC).isoformat()

        # Define success response that matches AWS API format
        success_response = {
            'CapacityReservation': {
                'CapacityReservationId': 'cr-mock-12345',
                'OwnerId': '123456789012',
                'CapacityReservationArn': 'arn:aws:ec2:region:123456789012:capacity-reservation/cr-mock-12345',
                'InstanceType': self.args.instance_type,
                'InstancePlatform': self.args.platform,
                'AvailabilityZone': self.args.availability_zone,
                'Tenancy': self.args.tenancy,
                'TotalInstanceCount': self.args.instance_count,
                'AvailableInstanceCount': self.args.instance_count,
                'EbsOptimized': self.args.ebs_optimized,
                'EphemeralStorage': False,
                'State': 'active',
                'StartDate': current_time,
                'EndDateType': self.args.end_date_type,
                'InstanceMatchCriteria': 'open',
                'CreateDate': current_time,
                'Tags': [{'Key': k, 'Value': v} for k, v in self.args.tags.items()],
                'OutpostArn': '',
                'CapacityReservationFleetId': '',
                'PlacementGroupArn': '',
                'CapacityAllocations': [],
                'ReservationType': 'standard',
                'UnusedReservationBillingOwnerId': '123456789012',  # Must be 12 digits
                'DeliveryPreference': 'none'
            }
        }

        # Add EndDate to response only if it's a limited reservation
        if self.args.end_date_type == 'limited' and self.args.end_date:
            success_response['CapacityReservation']['EndDate'] = self.args.end_date

        # Add simulation responses
        if self.max_retries > 0:
            # Add error responses for all but the last attempt
            for _ in range(min(2, self.max_retries)):
                self.stubber.add_client_error(
                    'create_capacity_reservation',
                    'InsufficientCapacityError',
                    'There is not enough capacity available for your request.',
                    expected_params=expected_params
                )

        # Add successful response for the last attempt
        self.stubber.add_response('create_capacity_reservation', success_response, expected_params)
        self.stubber.activate()

    def create_reservation(self):
        """Create the capacity reservation"""
        start_time = time.time()
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            elapsed_time = time.time() - start_time

            if elapsed_time >= self.max_wait_time:
                logger.error(f"Maximum wait time of {self.max_wait_time} seconds exceeded")
                return False, None

            try:
                logger.info(f"\nAttempt {attempt} of {self.max_retries}")

                # Build the API parameters
                params = {
                    'InstanceType': self.args.instance_type,
                    'InstancePlatform': self.args.platform,
                    'AvailabilityZone': self.args.availability_zone,
                    'Tenancy': self.args.tenancy,
                    'InstanceCount': self.args.instance_count,
                    'EbsOptimized': self.args.ebs_optimized,
                    'EndDateType': self.args.end_date_type,
                    'TagSpecifications': [{
                        'ResourceType': 'capacity-reservation',
                        'Tags': [{'Key': k, 'Value': v} for k, v in self.args.tags.items()]
                    }] if self.args.tags else []
                }

                # Add EndDate only if it's a limited reservation
                if self.args.end_date_type == 'limited' and self.args.end_date:
                    params['EndDate'] = self.args.end_date

                response = self.ec2_client.create_capacity_reservation(**params)
                reservation = response['CapacityReservation']
                
                logger.info(f"Successfully created capacity reservation: {reservation['CapacityReservationId']}")
                logger.info(f"Status: {reservation['State']}")
                logger.info(f"Instance Type: {reservation['InstanceType']}")
                logger.info(f"Instance Count: {reservation['TotalInstanceCount']}")
                logger.info(f"Platform: {reservation['InstancePlatform']}")
                logger.info(f"Availability Zone: {reservation['AvailabilityZone']}")
                
                return True, reservation

            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                last_error = e

                if error_code == 'InsufficientCapacityError':
                    logger.warning(f"Insufficient capacity: {error_message}")
                    
                    if attempt < self.max_retries:
                        logger.info(f"Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Error creating capacity reservation: {error_code} - {error_message}")
                    break

        if last_error:
            logger.error(f"Failed after {attempt} attempts. Last error: {str(last_error)}")
        return False, None

def main():
    args = parse_args()
    manager = CapacityReservationManager(args)
    
    success, result = manager.create_reservation()
    
    if success:
        logger.info("\nReservation details:")
        for key, value in result.items():
            logger.info(f"{key}: {value}")
    else:
        logger.error(f"\nFailed to create reservation: {result}")
        exit(1)

if __name__ == "__main__":
    main()
