from pulumi import Config, Output, export
import pulumi_aws as aws
import pulumi_awsx as awsx

config = Config()
container_port = config.get_int("containerPort", 5000)
cpu = config.get_int("cpu", 512)
memory = config.get_int("memory", 128)

tags = {
    "Env"  : "Dev",
    "BU"   : "Development",
    "Owner" : "SRE",
    "Git:repo" : "http://github.com",
}


def Merge(dict_1, dict_2):
	result = dict_1 | dict_2
	return result

#create VPC
vpc = awsx.ec2.Vpc("vpc")
public_alb_sg = aws.ec2.SecurityGroup("ext_alb_sg",
    vpc_id=vpc.vpc_id,
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )],
    ingress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=80,
        to_port=80,
        protocol="6",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )])

int_alb_sg = aws.ec2.SecurityGroup("int_alb_sg",
    vpc_id=vpc.vpc_id,
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        ipv6_cidr_blocks=["::/0"],
    )],
    ingress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=80,
        to_port=80,
        protocol="6",
        cidr_blocks=["10.0.0.0/8"],
        ipv6_cidr_blocks=["::/0"],
    )])

# An ECS cluster to deploy into
cluster = aws.ecs.Cluster(
    "cluster",
    tags=tags)

# Deploy infra-web application and create Public ALB
# An ALB to serve the container endpoint to the internet
public_alb = awsx.lb.ApplicationLoadBalancer(
    "loadbalancer", 
    default_target_group_port=5000,
    tags=Merge(tags, {"Name" : "infra-web"}))

# An ECR repository to store our application's container image
repo = awsx.ecr.Repository(
    "infra-web",

    awsx.ecr.RepositoryArgs(
    name="infra-web",
    force_delete=True,
    tags=Merge(tags, {"Name" : "infra-web"})
))

# Build and publish our application's container image from ./app to the ECR repository
# image = awsx.ecr.Image(
#      "image",
#      repository_url=repo.url,
#      path="../infra-team-test/infra-web")

# Deploy an ECS Service on Fargate to host the application container
infra_web_service = awsx.ecs.FargateService(
    "infra-web",
    cluster=cluster.arn,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=vpc.private_subnet_ids,
        security_groups=[public_alb_sg.id]
    ),
    task_definition_args=awsx.ecs.FargateServiceTaskDefinitionArgs(
        container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
            #image=image.image_uri,
            image="266080322197.dkr.ecr.us-east-1.amazonaws.com/infra-web",
            cpu=cpu,
            memory=memory,
            essential=True,
            port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                container_port=container_port,
                host_port=container_port,
                target_group=public_alb.default_target_group,
            )],
        ),
    ),
    
    tags=Merge(tags, {"Name" : "infra-web"}))

# Deploy infra-api application and create Internal ALB
# An ALB to serve the container endpoint to the internet
private_alb = awsx.lb.ApplicationLoadBalancer(
    "private-alb", 
    default_target_group_port=5000,
    tags=Merge(tags, {"Name" : "infra-api"}))

# An ECR repository to store our application's container image
repo = awsx.ecr.Repository("infra-api", awsx.ecr.RepositoryArgs(
    name="infra-api",
    force_delete=True,
    tags=Merge(tags, {"Name" : "infra-api"})
))

# Build and publish our application's container image from ./infra-api to the ECR repository
# image = awsx.ecr.Image(
#      "image",
#      repository_url=repo.url,
#      path="../infra-team-test/infra-api")

# Deploy an ECS Service on Fargate to host the application container
infra_api_service = awsx.ecs.FargateService(
    "infra-api",
    cluster=cluster.arn,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=vpc.private_subnet_ids,
        security_groups=[public_alb_sg.id,int_alb_sg.id]
    ),

    task_definition_args=awsx.ecs.FargateServiceTaskDefinitionArgs(
        container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
            #image=image.image_uri,
            image="266080322197.dkr.ecr.us-east-1.amazonaws.com/infra-api",
            cpu=cpu,
            memory=memory,
            essential=True,
            port_mappings=[awsx.ecs.TaskDefinitionPortMappingArgs(
                container_port=container_port,
                host_port=container_port,
                target_group=private_alb.default_target_group,
            )],
        ),
    ),
    
    tags = Merge(tags, {"Name" : "infra-api"}))

# The URL at which the container's HTTP endpoint will be available
export("url", Output.concat("http://", public_alb.load_balancer.dns_name))
export("url", Output.concat("http://", private_alb.load_balancer.dns_name))
