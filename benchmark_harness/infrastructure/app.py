#!/usr/bin/env python3
"""
CAA Benchmark Harness Infrastructure
Simplified CDK app for EKS cluster with proper networking
"""

import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_iam as iam,
    aws_ecr as ecr,
    CfnOutput,
    Duration,
    RemovalPolicy
)

class BenchmarkHarnessStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC with large address space for massive scaling
        self.vpc = ec2.Vpc(
            self, "BenchmarkVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),  # Large address space
            max_azs=3,
            subnet_configuration=[
                # Public subnets for load balancers
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=20,  # /20 subnets = 4,094 IPs each
                ),
                # Private subnets for EKS nodes
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20,  # /20 subnets = 4,094 IPs each
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # Create EKS cluster with latest Kubernetes version
        self.cluster = eks.Cluster(
            self, "BenchmarkCluster",
            cluster_name="benchmark-harness-cluster",
            version=eks.KubernetesVersion.V1_28,  # Latest available version
            vpc=self.vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
            default_capacity=0,  # We'll add managed node groups separately
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            cluster_logging=[
                eks.ClusterLoggingTypes.API,
                eks.ClusterLoggingTypes.AUDIT,
                eks.ClusterLoggingTypes.AUTHENTICATOR,
                eks.ClusterLoggingTypes.CONTROLLER_MANAGER,
                eks.ClusterLoggingTypes.SCHEDULER,
            ],
        )

        # Create IAM role for EKS nodes
        node_role = iam.Role(
            self, "NodeRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
            ],
        )

        # Primary node group for general workloads
        primary_nodegroup = self.cluster.add_nodegroup_capacity(
            "PrimaryNodes",
            instance_types=[
                ec2.InstanceType("c5.2xlarge"),  # 8 vCPU, 16 GB RAM
                ec2.InstanceType("c5.4xlarge"),  # 16 vCPU, 32 GB RAM
            ],
            min_size=10,
            max_size=100,
            desired_size=20,
            disk_size=100,
            ami_type=eks.NodegroupAmiType.AL2_X86_64,
            capacity_type=eks.CapacityType.ON_DEMAND,
            node_role=node_role,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            labels={
                "workload": "benchmarks",
                "node-type": "primary"
            },
            tags={
                "Name": "benchmark-harness-primary-node",
                "Environment": "benchmark-testing"
            }
        )

        # High-performance node group for intensive benchmarks
        performance_nodegroup = self.cluster.add_nodegroup_capacity(
            "PerformanceNodes",
            instance_types=[
                ec2.InstanceType("c5.9xlarge"),   # 36 vCPU, 72 GB RAM
                ec2.InstanceType("c5.12xlarge"),  # 48 vCPU, 96 GB RAM
            ],
            min_size=5,
            max_size=50,
            desired_size=10,
            disk_size=200,
            ami_type=eks.NodegroupAmiType.AL2_X86_64,
            capacity_type=eks.CapacityType.ON_DEMAND,
            node_role=node_role,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            labels={
                "workload": "high-performance",
                "node-type": "performance"
            },
            tags={
                "Name": "benchmark-harness-performance-node",
                "Environment": "benchmark-testing"
            }
        )

        # Create ECR repositories for container images
        self.create_ecr_repositories()

        # Create namespace for benchmarks
        benchmark_namespace = self.cluster.add_manifest("BenchmarkNamespace", {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "benchmark-harness",
                "labels": {
                    "name": "benchmark-harness"
                }
            }
        })

        # Install AWS Load Balancer Controller
        self.cluster.add_helm_chart(
            "AWSLoadBalancerController",
            chart="aws-load-balancer-controller",
            repository="https://aws.github.io/eks-charts",
            namespace="kube-system",
            values={
                "clusterName": self.cluster.cluster_name,
                "serviceAccount": {
                    "create": False,
                    "name": "aws-load-balancer-controller"
                }
            }
        )

        # Create service account for AWS Load Balancer Controller
        lb_service_account = self.cluster.add_service_account(
            "AWSLoadBalancerControllerServiceAccount",
            name="aws-load-balancer-controller",
            namespace="kube-system"
        )

        # Add IAM policy for Load Balancer Controller
        lb_policy_document = iam.PolicyDocument.from_json({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "iam:CreateServiceLinkedRole",
                        "ec2:DescribeAccountAttributes",
                        "ec2:DescribeAddresses",
                        "ec2:DescribeAvailabilityZones",
                        "ec2:DescribeInternetGateways",
                        "ec2:DescribeVpcs",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeSecurityGroups",
                        "ec2:DescribeInstances",
                        "ec2:DescribeNetworkInterfaces",
                        "ec2:DescribeTags",
                        "ec2:GetCoipPoolUsage",
                        "ec2:DescribeCoipPools",
                        "elasticloadbalancing:DescribeLoadBalancers",
                        "elasticloadbalancing:DescribeLoadBalancerAttributes",
                        "elasticloadbalancing:DescribeListeners",
                        "elasticloadbalancing:DescribeListenerCertificates",
                        "elasticloadbalancing:DescribeSSLPolicies",
                        "elasticloadbalancing:DescribeRules",
                        "elasticloadbalancing:DescribeTargetGroups",
                        "elasticloadbalancing:DescribeTargetGroupAttributes",
                        "elasticloadbalancing:DescribeTargetHealth",
                        "elasticloadbalancing:DescribeTags"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:DescribeUserPoolClient",
                        "acm:ListCertificates",
                        "acm:DescribeCertificate",
                        "iam:ListServerCertificates",
                        "iam:GetServerCertificate",
                        "waf-regional:GetWebACL",
                        "waf-regional:GetWebACLForResource",
                        "waf-regional:AssociateWebACL",
                        "waf-regional:DisassociateWebACL",
                        "wafv2:GetWebACL",
                        "wafv2:GetWebACLForResource",
                        "wafv2:AssociateWebACL",
                        "wafv2:DisassociateWebACL",
                        "shield:DescribeProtection",
                        "shield:GetSubscriptionState",
                        "shield:DescribeSubscription",
                        "shield:CreateProtection",
                        "shield:DeleteProtection"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:CreateSecurityGroup",
                        "ec2:CreateTags"
                    ],
                    "Resource": "arn:aws:ec2:*:*:security-group/*",
                    "Condition": {
                        "StringEquals": {
                            "ec2:CreateAction": "CreateSecurityGroup"
                        },
                        "Null": {
                            "aws:RequestTag/elbv2.k8s.aws/cluster": "false"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "elasticloadbalancing:CreateLoadBalancer",
                        "elasticloadbalancing:CreateTargetGroup"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "Null": {
                            "aws:RequestTag/elbv2.k8s.aws/cluster": "false"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "elasticloadbalancing:CreateListener",
                        "elasticloadbalancing:DeleteListener",
                        "elasticloadbalancing:CreateRule",
                        "elasticloadbalancing:DeleteRule"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "elasticloadbalancing:AddTags",
                        "elasticloadbalancing:RemoveTags"
                    ],
                    "Resource": [
                        "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
                        "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
                        "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
                    ],
                    "Condition": {
                        "Null": {
                            "aws:RequestTag/elbv2.k8s.aws/cluster": "true",
                            "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "elasticloadbalancing:ModifyLoadBalancerAttributes",
                        "elasticloadbalancing:SetIpAddressType",
                        "elasticloadbalancing:SetSecurityGroups",
                        "elasticloadbalancing:SetSubnets",
                        "elasticloadbalancing:DeleteLoadBalancer",
                        "elasticloadbalancing:ModifyTargetGroup",
                        "elasticloadbalancing:ModifyTargetGroupAttributes",
                        "elasticloadbalancing:DeleteTargetGroup"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "Null": {
                            "aws:ResourceTag/elbv2.k8s.aws/cluster": "false"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "elasticloadbalancing:RegisterTargets",
                        "elasticloadbalancing:DeregisterTargets"
                    ],
                    "Resource": "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:CreateSecurityGroup",
                        "ec2:CreateTags",
                        "ec2:DeleteTags",
                        "ec2:AuthorizeSecurityGroupIngress",
                        "ec2:RevokeSecurityGroupIngress",
                        "ec2:DeleteSecurityGroup"
                    ],
                    "Resource": "*"
                }
            ]
        })

        lb_service_account.role.attach_inline_policy(
            iam.Policy(self, "AWSLoadBalancerControllerPolicy", document=lb_policy_document)
        )

        # Outputs
        CfnOutput(self, "ClusterName", value=self.cluster.cluster_name)
        CfnOutput(self, "ClusterEndpoint", value=self.cluster.cluster_endpoint)
        CfnOutput(self, "ClusterArn", value=self.cluster.cluster_arn)
        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(self, "KubectlCommand", 
                 value=f"aws eks update-kubeconfig --region {self.region} --name {self.cluster.cluster_name}")

    def create_ecr_repositories(self):
        """Create ECR repositories for benchmark container images"""
        repositories = [
            "benchmark-harness/xben-web-apps",
            "benchmark-harness/xben-databases", 
            "benchmark-harness/xben-services",
            "benchmark-harness/caa-agent"
        ]

        for repo_name in repositories:
            ecr.Repository(
                self, f"ECRRepo{repo_name.replace('/', '').replace('-', '')}",
                repository_name=repo_name,
                removal_policy=RemovalPolicy.DESTROY,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Keep last 10 images",
                        max_image_count=10
                    )
                ]
            )

app = cdk.App()
BenchmarkHarnessStack(app, "BenchmarkHarnessStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1"
    )
)

app.synth()