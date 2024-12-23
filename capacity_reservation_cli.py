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
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common instance types by use case
INSTANCE_TYPE_CHOICES = {
    'general_purpose': [
        # T instances (burstable)
        't2.nano', 't2.micro', 't2.small', 't2.medium', 't2.large', 't2.xlarge', 't2.2xlarge',
        't3.nano', 't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
        't3a.nano', 't3a.micro', 't3a.small', 't3a.medium', 't3a.large', 't3a.xlarge', 't3a.2xlarge',
        # M instances (standard)
        'm4.large', 'm4.xlarge', 'm4.2xlarge', 'm4.4xlarge', 'm4.10xlarge', 'm4.16xlarge',
        'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge', 'm5.8xlarge', 'm5.12xlarge', 'm5.16xlarge', 'm5.24xlarge',
        'm5a.large', 'm5a.xlarge', 'm5a.2xlarge', 'm5a.4xlarge', 'm5a.8xlarge', 'm5a.12xlarge', 'm5a.16xlarge', 'm5a.24xlarge',
        'm6a.large', 'm6a.xlarge', 'm6a.2xlarge', 'm6a.4xlarge', 'm6a.8xlarge', 'm6a.12xlarge', 'm6a.16xlarge', 'm6a.24xlarge', 'm6a.32xlarge', 'm6a.48xlarge',
        'm6g.medium', 'm6g.large', 'm6g.xlarge', 'm6g.2xlarge', 'm6g.4xlarge', 'm6g.8xlarge', 'm6g.12xlarge', 'm6g.16xlarge',
        'm6i.large', 'm6i.xlarge', 'm6i.2xlarge', 'm6i.4xlarge', 'm6i.8xlarge', 'm6i.12xlarge', 'm6i.16xlarge', 'm6i.24xlarge', 'm6i.32xlarge',
        'm7g.medium', 'm7g.large', 'm7g.xlarge', 'm7g.2xlarge', 'm7g.4xlarge', 'm7g.8xlarge', 'm7g.12xlarge', 'm7g.16xlarge'
    ],
    'compute_optimized': [
        # C instances
        'c4.large', 'c4.xlarge', 'c4.2xlarge', 'c4.4xlarge', 'c4.8xlarge',
        'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge', 'c5.9xlarge', 'c5.12xlarge', 'c5.18xlarge', 'c5.24xlarge',
        'c5a.large', 'c5a.xlarge', 'c5a.2xlarge', 'c5a.4xlarge', 'c5a.8xlarge', 'c5a.12xlarge', 'c5a.16xlarge', 'c5a.24xlarge',
        'c6a.large', 'c6a.xlarge', 'c6a.2xlarge', 'c6a.4xlarge', 'c6a.8xlarge', 'c6a.12xlarge', 'c6a.16xlarge', 'c6a.24xlarge', 'c6a.32xlarge', 'c6a.48xlarge',
        'c6g.medium', 'c6g.large', 'c6g.xlarge', 'c6g.2xlarge', 'c6g.4xlarge', 'c6g.8xlarge', 'c6g.12xlarge', 'c6g.16xlarge',
        'c6i.large', 'c6i.xlarge', 'c6i.2xlarge', 'c6i.4xlarge', 'c6i.8xlarge', 'c6i.12xlarge', 'c6i.16xlarge', 'c6i.24xlarge', 'c6i.32xlarge',
        'c7g.medium', 'c7g.large', 'c7g.xlarge', 'c7g.2xlarge', 'c7g.4xlarge', 'c7g.8xlarge', 'c7g.12xlarge', 'c7g.16xlarge'
    ],
    'memory_optimized': [
        # R instances
        'r4.large', 'r4.xlarge', 'r4.2xlarge', 'r4.4xlarge', 'r4.8xlarge', 'r4.16xlarge',
        'r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge', 'r5.8xlarge', 'r5.12xlarge', 'r5.16xlarge', 'r5.24xlarge',
        'r5a.large', 'r5a.xlarge', 'r5a.2xlarge', 'r5a.4xlarge', 'r5a.8xlarge', 'r5a.12xlarge', 'r5a.16xlarge', 'r5a.24xlarge',
        'r6a.large', 'r6a.xlarge', 'r6a.2xlarge', 'r6a.4xlarge', 'r6a.8xlarge', 'r6a.12xlarge', 'r6a.16xlarge', 'r6a.24xlarge', 'r6a.32xlarge', 'r6a.48xlarge',
        'r6g.medium', 'r6g.large', 'r6g.xlarge', 'r6g.2xlarge', 'r6g.4xlarge', 'r6g.8xlarge', 'r6g.12xlarge', 'r6g.16xlarge',
        'r6i.large', 'r6i.xlarge', 'r6i.2xlarge', 'r6i.4xlarge', 'r6i.8xlarge', 'r6i.12xlarge', 'r6i.16xlarge', 'r6i.24xlarge', 'r6i.32xlarge',
        # X instances (memory intensive)
        'x1.16xlarge', 'x1.32xlarge',
        'x1e.xlarge', 'x1e.2xlarge', 'x1e.4xlarge', 'x1e.8xlarge', 'x1e.16xlarge', 'x1e.32xlarge',
        'x2gd.medium', 'x2gd.large', 'x2gd.xlarge', 'x2gd.2xlarge', 'x2gd.4xlarge', 'x2gd.8xlarge', 'x2gd.12xlarge', 'x2gd.16xlarge',
        # High Memory instances
        'u-3tb1.56xlarge', 'u-6tb1.56xlarge', 'u-6tb1.112xlarge', 'u-9tb1.112xlarge', 'u-12tb1.112xlarge'
    ],
    'storage_optimized': [
        # I instances (NVMe SSD)
        'i3.large', 'i3.xlarge', 'i3.2xlarge', 'i3.4xlarge', 'i3.8xlarge', 'i3.16xlarge', 'i3.metal',
        'i3en.large', 'i3en.xlarge', 'i3en.2xlarge', 'i3en.3xlarge', 'i3en.6xlarge', 'i3en.12xlarge', 'i3en.24xlarge', 'i3en.metal',
        # D instances (HDD)
        'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge', 'd2.8xlarge',
        'd3.xlarge', 'd3.2xlarge', 'd3.4xlarge', 'd3.8xlarge',
        'd3en.xlarge', 'd3en.2xlarge', 'd3en.4xlarge', 'd3en.6xlarge', 'd3en.8xlarge', 'd3en.12xlarge'
    ],
    'accelerated_computing': [
        # P instances (GPU)
        'p2.xlarge', 'p2.8xlarge', 'p2.16xlarge',
        'p3.2xlarge', 'p3.8xlarge', 'p3.16xlarge',
        'p3dn.24xlarge',
        'p4d.24xlarge',
        'p4de.24xlarge',
        # G instances (Graphics)
        'g3.4xlarge', 'g3.8xlarge', 'g3.16xlarge',
        'g4dn.xlarge', 'g4dn.2xlarge', 'g4dn.4xlarge', 'g4dn.8xlarge', 'g4dn.12xlarge', 'g4dn.16xlarge', 'g4dn.metal',
        'g5.xlarge', 'g5.2xlarge', 'g5.4xlarge', 'g5.8xlarge', 'g5.12xlarge', 'g5.16xlarge', 'g5.24xlarge', 'g5.48xlarge',
        # F instances (FPGA)
        'f1.2xlarge', 'f1.4xlarge', 'f1.16xlarge',
        # Inf instances (Inferentia)
        'inf1.xlarge', 'inf1.2xlarge', 'inf1.6xlarge', 'inf1.24xlarge',
        'inf2.xlarge', 'inf2.8xlarge', 'inf2.24xlarge', 'inf2.48xlarge',
        # Trn instances (Trainium)
        'trn1.2xlarge', 'trn1.32xlarge',
        'trn1n.32xlarge'
    ],
    'hpc_optimized': [
        # Hpc instances
        'hpc6a.48xlarge',
        'hpc6id.32xlarge',
        'hpc7g.4xlarge', 'hpc7g.8xlarge', 'hpc7g.16xlarge'
    ]
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
    """Get choices through interactive prompts"""
    
    questions = [
        # Instance Type Selection (two-step process)
        inquirer.List('instance_type_category',
                     message="Select instance type category",
                     choices=list(INSTANCE_TYPE_CHOICES.keys()),
                     default='general_purpose'),
        
        # Dynamic instance type choices based on category
        inquirer.List('instance_type',
                     message="Choose instance type",
                     # Lambda function is used to return dynamic list of instance type choices
                     # - it takes the answers dictionary as a parameter
                     # - it returns the list of instance type choices for the selected category
                     choices=lambda answers: INSTANCE_TYPE_CHOICES[answers['instance_type_category']]),
        
        # Instance Count
        inquirer.Text('instance_count',
                     message="Enter number of instances to reserve",
                     # Lambda function used as inline validator for inquirer
                     # - Takes two params: _ (unused answers dict) and x (current input)
                     # - Returns True if input is valid (digits only AND positive number)
                     # - Used here because validation is simple and specific to this field
                     # - Alternative would be a separate named function if more complex validation needed
                     validate=lambda _, x: x.isdigit() and int(x) > 0),
        
        # Platform Selection
        inquirer.List('platform',
                     message="Select platform",
                     choices=PLATFORM_CHOICES,
                     default='Linux/UNIX'),

        # Region and AZ Selection
        inquirer.List('region',
                     message="Select region",
                     choices=REGION_CHOICES,
                     default='us-west-2'),
        
        inquirer.Text('availability_zone',
                     message="Enter availability zone (leave empty for auto-select)",
                     default=''),

        # Instance Settings
        inquirer.Confirm('ebs_optimized',
                        message="Enable EBS optimization?",
                        default=False),
        
        inquirer.List('tenancy',
                     message="Select tenancy",
                     choices=['default', 'dedicated'],
                     default='default'),

        # Reservation Settings
        inquirer.List('end_date_type',
                     message="Select end date type",
                     choices=['unlimited', 'limited'],
                     default='unlimited'),

        # End date (only if limited)
        inquirer.Text('end_date',
                     message="Enter end date (ISO 8601 format, e.g., 2024-12-31T23:59:59)",
                     ignore=lambda answers: answers['end_date_type'] == 'unlimited',
                     validate=lambda _, x: len(x) > 0),

        # Tags
        inquirer.Confirm('add_tags',
                        message="Would you like to add tags?",
                        default=False)
    ]

    answers = inquirer.prompt(questions)
    if not answers:
        sys.exit(1)

    # Handle availability zone default if empty
    if not answers['availability_zone']:
        answers['availability_zone'] = f"{answers['region']}a"

    # Handle tags if user wants to add them
    if answers.pop('add_tags', False):
        tags = {}
        while True:
            tag_questions = [
                inquirer.Text('key',
                            message="Enter tag key"),
                inquirer.Text('value',
                            message="Enter tag value"),
                inquirer.Confirm('add_another',
                               message="Add another tag?",
                               default=False)
            ]
            tag_answers = inquirer.prompt(tag_questions)
            if not tag_answers:
                break
            
            tags[tag_answers['key']] = tag_answers['value']
            if not tag_answers['add_another']:
                break
        answers['tags'] = tags
    else:
        answers['tags'] = {}

    # Display summary of choices
    logger.info("\nCapacity Reservation Parameters Summary:")
    logger.info("-" * 40)
    logger.info(f"Instance Type:      {answers['instance_type']}")
    logger.info(f"Instance Count:     {answers['instance_count']}")
    logger.info(f"Platform:           {answers['platform']}")
    logger.info(f"Region:            {answers['region']}")
    logger.info(f"Availability Zone: {answers['availability_zone']}")
    logger.info(f"EBS Optimized:     {'Yes' if answers['ebs_optimized'] else 'No'}")
    logger.info(f"Tenancy:           {answers['tenancy']}")
    logger.info(f"End Date Type:     {answers['end_date_type']}")
    if answers['end_date_type'] == 'limited':
        logger.info(f"End Date:          {answers['end_date']}")
    if answers['tags']:
        logger.info("\nTags:")
        for key, value in answers['tags'].items():
            logger.info(f"  {key}: {value}")
    logger.info("-" * 40)
    
    # Prompt for confirmation
    confirm = inquirer.confirm("Proceed with these parameters?", default=True)
    if not confirm:
        logger.info("Operation cancelled by user")
        sys.exit(0)

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

def get_aws_profiles():
    """Get available AWS profiles from credentials and config files"""
    import boto3.session
    return boto3.session.Session().available_profiles

def setup_aws_session(profile_name=None):
    """Setup AWS session with optional profile"""
    import boto3
    try:
        # ############################################################
        # WARNING: This will create a real AWS session
        # This will:
        # 1. Load real AWS credentials
        # 2. Test access to your AWS account
        # 3. Enable real AWS API calls
        # ############################################################
        session = boto3.Session(profile_name=profile_name)
        # Test the credentials
        sts = session.client('sts')
        sts.get_caller_identity()
        return session
    except Exception as e:
        logger.error(f"Failed to setup AWS session with profile '{profile_name}': {str(e)}")
        return None

class CapacityReservationManager:
    def __init__(self, args):
        """Initialize with CLI arguments"""
        # Convert dictionary to namespace if needed
        if isinstance(args, dict):
            from types import SimpleNamespace
            args_dict = args.copy()  # Make a copy to avoid modifying the original
            # Ensure all required attributes exist with defaults
            defaults = {
                'availability_zone': f"{args_dict.get('region', 'us-east-1')}a",
                'end_date': None,
                'simulation_mode': True,
                'max_retries': 3,
                'retry_delay': 1,
                'max_wait_time': 3600,
                'log_level': 'INFO',
                'retry_config': 'QUICK_RETRY',
                'tags': {},
                'region': 'us-east-1'
            }
            # Update defaults with provided values
            for key, value in defaults.items():
                if key not in args_dict:
                    args_dict[key] = value
            self.args = SimpleNamespace(**args_dict)
        else:
            self.args = args

        # Configure logging
        logging.getLogger().setLevel(getattr(logging, self.args.log_level))

        # Set retry configuration
        self.config = RETRY_CONFIG[self.args.retry_config]
        self.max_retries = getattr(self.args, 'custom_max_retries', None) or self.config['max_retries']
        self.retry_delay = getattr(self.args, 'custom_retry_delay', None) or self.config['retry_delay_seconds']
        self.max_wait_time = getattr(self.args, 'max_wait_time', 3600)

        if not self.args.simulation_mode:
            # ############################################################
            # WARNING: Non-simulation mode - Will use real AWS credentials
            # This will:
            # 1. Access your AWS account
            # 2. Use your configured AWS profile
            # 3. Enable real AWS API calls
            # ############################################################
            
            # Get available profiles
            profiles = get_aws_profiles()
            
            if not profiles:
                logger.warning("No AWS profiles found. Please configure AWS credentials.")
                sys.exit(1)
            
            # Let user choose profile if not in simulation mode
            profile_questions = [
                inquirer.List('profile',
                            message="Choose AWS Profile",
                            choices=profiles,
                            default=profiles[0] if profiles else None)
            ]
            
            profile_answers = inquirer.prompt(profile_questions)
            if not profile_answers:
                logger.error("AWS profile selection cancelled")
                sys.exit(1)
                
            # Setup AWS session with chosen profile
            session = setup_aws_session(profile_answers['profile'])
            if not session:
                logger.error("Failed to setup AWS session")
                sys.exit(1)
                
            self.ec2_client = session.client('ec2', region_name=self.args.region)
            logger.info(f"Using AWS Profile: {profile_answers['profile']}")
            
            # Get and display account info
            sts = session.client('sts')
            account_id = sts.get_caller_identity()['Account']
            logger.info(f"AWS Account ID: {account_id}")
        else:
            # Simulation mode - No real AWS calls will be made
            self.ec2_client = boto3.client('ec2', region_name=self.args.region)
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
            'InstanceCount': int(self.args.instance_count),  # Convert to int
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

        # Convert instance count to int for response
        instance_count = int(self.args.instance_count)

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
                'TotalInstanceCount': instance_count,  # Use converted int
                'AvailableInstanceCount': instance_count,  # Use converted int
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
                    'InstanceCount': int(self.args.instance_count),  # Convert to int
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

                # ############################################################
                # WARNING: This will make a real AWS API call if not in simulation mode
                # This will:
                # 1. Create an actual capacity reservation in your AWS account
                # 2. Incur charges for the reserved capacity
                # 3. Count against your service quotas
                # ############################################################
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
