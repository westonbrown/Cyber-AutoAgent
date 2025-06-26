from aws_cdk import (
    Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput,
    Tags,
)
from constructs import Construct

class CAATestHarnessStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get SSH key name from context or use default
        ssh_key_name = self.node.try_get_context("ssh_key")

        # Create a VPC with a single public subnet
        vpc = ec2.Vpc(
            self, "VPC",
            max_azs=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            ],
            nat_gateways=0
        )

        # Create a security group for the Kali instance
        security_group = ec2.SecurityGroup(
            self, "KaliSecurityGroup",
            vpc=vpc,
            description="Security group for Kali Linux instance",
            allow_all_outbound=True
        )

        # Allow SSH access
        security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22),
            "Allow SSH access"
        )

        # Create IAM role for the Kali instance
        role = iam.Role(
            self, "KaliInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )

        # Add permissions to access AWS Bedrock
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]
            )
        )

        # Add permissions to access CloudWatch Logs
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess")
        )

        # Add SSM Managed Instance Core policy
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )

        # Check if we should create a new key pair
        key_pair = None
        if not ssh_key_name:
            # Create a new key pair
            key_pair = ec2.CfnKeyPair(
                self, "KaliKeyPair",
                key_name=f"caa-test-key-{self.stack_name.lower()}"
            )
            
            # Store the private key in SSM Parameter Store
            ssm_param = ssm.StringParameter(
                self, "KaliKeyPrivate",
                parameter_name="/caa-test-harness/ssh-key",
                string_value=key_pair.get_att("KeyMaterial").to_string(),
                description="SSH private key for CAA Test Harness",
            )
            
            ssh_key_name = key_pair.key_name

        # Create the Kali Linux EC2 instance
        instance = ec2.Instance(
            self, "KaliInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.large"),
            machine_image=ec2.MachineImage.generic_linux({
                "us-east-1": "ami-05765033efd970565",  # Kali Linux AMI
            }),
            security_group=security_group,
            role=role,
            key_name=ssh_key_name,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=100,  # 100 GB for Docker images and results
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                    )
                )
            ]
        )

        # Add tags to the instance
        Tags.of(instance).add("Name", "CAA-Test-Harness-Kali")
        Tags.of(instance).add("Project", "CAA-Test-Harness")

        # Output important information
        CfnOutput(
            self, "InstanceId",
            value=instance.instance_id,
            description="ID of the Kali Linux instance"
        )
        
        CfnOutput(
            self, "InstancePublicIp",
            value=instance.instance_public_ip,
            description="Public IP address of the Kali Linux instance"
        )
        
        CfnOutput(
            self, "SSHCommand",
            value=f"ssh -i ~/.ssh/{ssh_key_name}.pem kali@{instance.instance_public_ip}",
            description="SSH command to connect to the instance"
        )
        
        if key_pair:
            CfnOutput(
                self, "SSHKeyRetrievalCommand",
                value=f"aws ssm get-parameter --name /caa-test-harness/ssh-key --with-decryption --query Parameter.Value --output text > ~/.ssh/{key_pair.key_name}.pem && chmod 600 ~/.ssh/{key_pair.key_name}.pem",
                description="Command to retrieve the SSH key"
            )