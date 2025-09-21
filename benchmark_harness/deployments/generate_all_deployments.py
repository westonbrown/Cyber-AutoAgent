#!/usr/bin/env python3
"""
Generate Kubernetes deployment manifests for all 104 benchmarks
with correct image names and container configurations.
"""

import os
import yaml
import json
import re

# Configuration
ECR_REGISTRY = "123456789999.dkr.ecr.us-east-1.amazonaws.com"  # Update this with your account ID
NAMESPACE = "benchmark-harness"
CONTAINERS_DIR = "../containers"

def get_database_dependencies(benchmark_id):
    """Get database dependencies from docker-compose.yml."""
    reference_compose_path = f"../../validation-benchmarks/benchmarks/{benchmark_id}/docker-compose.yml"
    if not os.path.exists(reference_compose_path):
        return []
    
    try:
        with open(reference_compose_path, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        services = compose_data.get('services', {})
        db_services = []
        
        for service_name, service_config in services.items():
            # Check for standard database images
            image = service_config.get('image', '')
            if any(db in image.lower() for db in ['mongo', 'mysql', 'postgres', 'redis']):
                db_services.append(service_name)
            
            # Check for services with database-like names or build contexts
            elif service_name in ['db', 'database', 'mysql', 'postgres', 'mongo', 'mongodb', 'redis']:
                db_services.append(service_name)
            
            # Check if service has a build context that might be a database
            elif 'build' in service_config:
                build_context = service_config['build']
                if isinstance(build_context, str):
                    build_path = build_context
                elif isinstance(build_context, dict):
                    build_path = build_context.get('context', '')
                else:
                    build_path = ''
                
                if any(db in build_path.lower() for db in ['mysql', 'postgres', 'mongo', 'redis', 'db']):
                    db_services.append(service_name)
        
        return db_services
    except Exception as e:
        print(f"Warning: Could not read compose file for {benchmark_id}: {e}")
        return []

def get_benchmark_components(benchmark_id):
    """Get all components for a benchmark by scanning its directory and docker-compose dependencies."""
    benchmark_dir = os.path.join(CONTAINERS_DIR, benchmark_id)
    components = []
    
    # Get components with Dockerfiles
    if os.path.exists(benchmark_dir):
        for item in os.listdir(benchmark_dir):
            item_path = os.path.join(benchmark_dir, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "Dockerfile")):
                components.append(item)
    
    # Add database dependencies from docker-compose.yml
    db_dependencies = get_database_dependencies(benchmark_id)
    for db in db_dependencies:
        if db not in components:
            components.append(db)
    
    return sorted(components)

def get_ecr_repo_for_component(component):
    """Determine ECR repository based on component type."""
    if component in ['db', 'mysql', 'postgres', 'mongodb']:
        return "benchmark-harness/xben-databases"
    elif any(keyword in component.lower() for keyword in ['service', 'router', 'haproxy', 'mitmproxy', 'nginx']):
        return "benchmark-harness/xben-services"
    else:
        return "benchmark-harness/xben-web-apps"

def get_port_from_dockerfile(benchmark_id, component):
    """Extract the exposed port from a Dockerfile, docker-compose.yml, and associated Python files."""
    component_dir = os.path.join(CONTAINERS_DIR, benchmark_id, component)
    dockerfile_path = os.path.join(component_dir, "Dockerfile")
    
    # First try to get port from reference docker-compose.yml
    reference_compose_path = f"../../validation-benchmarks/benchmarks/{benchmark_id}/docker-compose.yml"
    if os.path.exists(reference_compose_path):
        try:
            import yaml as yaml_lib
            with open(reference_compose_path, 'r') as f:
                compose_data = yaml_lib.safe_load(f)
            
            services = compose_data.get('services', {})
            if component in services:
                service = services[component]
                
                # Check 'ports' section first (has priority)
                ports = service.get('ports', [])
                if ports:
                    for port in ports:
                        if isinstance(port, int):
                            return port
                        elif isinstance(port, str) and ':' in port:
                            # Format like "8001:8001" or "8001"
                            return int(port.split(':')[0])
                        elif isinstance(port, str) and port.isdigit():
                            return int(port)
                
                # Check 'expose' section
                expose = service.get('expose', [])
                if expose:
                    for port in expose:
                        if isinstance(port, int):
                            return port
                        elif isinstance(port, str) and port.isdigit():
                            return int(port)
                        elif isinstance(port, str):
                            # Handle string format like "3306"
                            port_num = re.search(r'(\d+)', port)
                            if port_num:
                                return int(port_num.group(1))
                                
        except Exception as e:
            print(f"Warning: Could not read reference compose for port detection {benchmark_id}: {e}")
    
    if not os.path.exists(dockerfile_path):
        # Default ports based on component type
        if component in ['db', 'mysql', 'postgres']:
            return 3306
        elif component in ['mongo', 'mongodb']:
            return 27017
        elif component in ['redis']:
            return 6379
        else:
            return 80
    
    try:
        # Check Dockerfile
        with open(dockerfile_path, 'r') as f:
            dockerfile_content = f.read()
            
        # Look for EXPOSE directive
        expose_match = re.search(r'EXPOSE\s+(\d+)', dockerfile_content, re.IGNORECASE)
        if expose_match:
            return int(expose_match.group(1))
            
        # Look for --port in CMD directive
        port_match = re.search(r'--port[=\s]+(\d+)', dockerfile_content, re.IGNORECASE)
        if port_match:
            return int(port_match.group(1))
            
        # Look for Django runserver with port in CMD (both string and JSON array format)
        django_match = re.search(r'runserver["\s,]+[\d.]*:(\d+)', dockerfile_content)
        if django_match:
            return int(django_match.group(1))
        
        # Check for Flask apps - look in Python files for app.run with port
        for filename in ['app.py', 'main.py', 'server.py']:
            python_file = os.path.join(component_dir, filename)
            if os.path.exists(python_file):
                try:
                    with open(python_file, 'r') as f:
                        python_content = f.read()
                    
                    # Look for app.run with port parameter
                    flask_port_match = re.search(r'app\.run\([^)]*port\s*=\s*(\d+)', python_content)
                    if flask_port_match:
                        return int(flask_port_match.group(1))
                        
                except Exception:
                    continue
        
        # Look for common port patterns in Dockerfile
        if 'flask' in dockerfile_content.lower() and '5000' in dockerfile_content:
            return 5000
        if 'django' in dockerfile_content.lower() and '8000' in dockerfile_content:
            return 8000
        if 'node' in dockerfile_content.lower() and '3000' in dockerfile_content:
            return 3000
            
    except Exception as e:
        print(f"Warning: Could not read files for {benchmark_id}/{component}: {e}")
    
    # Default ports based on component type
    if component in ['db', 'mysql', 'postgres', 'mongodb']:
        return 3306
    else:
        return 80

def create_container_spec(benchmark_id, component):
    """Create container specification for a component."""
    # Check if this is a database service from docker-compose.yml
    reference_compose_path = f"../../validation-benchmarks/benchmarks/{benchmark_id}/docker-compose.yml"
    is_db_service = False
    db_image = None
    
    if os.path.exists(reference_compose_path):
        try:
            with open(reference_compose_path, 'r') as f:
                compose_data = yaml.safe_load(f)
            services = compose_data.get('services', {})
            if component in services:
                service_config = services[component]
                image = service_config.get('image', '')
                
                # Check for standard database images
                if any(db in image.lower() for db in ['mongo', 'mysql', 'postgres', 'redis']):
                    is_db_service = True
                    db_image = image
                
                # Check for database services by name or build context
                elif component in ['db', 'database', 'mysql', 'postgres', 'mongo', 'mongodb', 'redis']:
                    is_db_service = True
                    db_image = None  # Custom build, no standard image
                
                # Check if service has a build context that might be a database
                elif 'build' in service_config:
                    build_context = service_config['build']
                    if isinstance(build_context, str):
                        build_path = build_context
                    elif isinstance(build_context, dict):
                        build_path = build_context.get('context', '')
                    else:
                        build_path = ''
                    
                    if any(db in build_path.lower() for db in ['mysql', 'postgres', 'mongo', 'redis', 'db']):
                        is_db_service = True
                        db_image = None  # Custom build, no standard image
                        
        except Exception as e:
            print(f"Warning: Could not read compose file for {benchmark_id}: {e}")
    
    # Use standard Docker image for database services, custom ECR image for others
    if is_db_service and db_image:
        image_name = db_image
        # Set default database ports
        if 'mongo' in db_image.lower():
            port = 27017
        elif 'mysql' in db_image.lower():
            port = 3306
        elif 'postgres' in db_image.lower():
            port = 5432
        elif 'redis' in db_image.lower():
            port = 6379
        else:
            port = get_port_from_dockerfile(benchmark_id, component)
    else:
        ecr_repo = get_ecr_repo_for_component(component)
        image_name = f"{ECR_REGISTRY}/{ecr_repo}:{benchmark_id}-{component}-latest"
        # Get the correct port from the Dockerfile
        port = get_port_from_dockerfile(benchmark_id, component)
    
    # Base environment variables
    env_vars = [{
        "name": "FLAG",
        "valueFrom": {
            "secretKeyRef": {
                "name": f"{benchmark_id.lower()}-flag",
                "key": "flag"
            }
        }
    }]
    
    # Add environment variables based on reference docker-compose.yml files
    reference_compose_path = f"../../validation-benchmarks/benchmarks/{benchmark_id}/docker-compose.yml"
    if os.path.exists(reference_compose_path):
        try:
            import yaml as yaml_lib
            with open(reference_compose_path, 'r') as f:
                compose_data = yaml_lib.safe_load(f)
            
            # Find the service that matches our component
            services = compose_data.get('services', {})
            if component in services:
                service_env = services[component].get('environment', {})
                if isinstance(service_env, dict):
                    for key, value in service_env.items():
                        # Map docker-compose service names to Kubernetes service names
                        if key == 'SERVER_HOSTNAME' and isinstance(value, str):
                            # Convert docker-compose service name to Kubernetes service name
                            k8s_service_name = f"{benchmark_id.lower()}-{value.replace('_', '-')}-service"
                            env_vars.append({"name": key, "value": k8s_service_name})
                        elif key == 'MONGO_URI' and isinstance(value, str):
                            # Replace docker-compose service names in MongoDB URI
                            updated_uri = value.replace('mongodb://mongo:', f'mongodb://{benchmark_id.lower()}-mongo-service:')
                            env_vars.append({"name": key, "value": updated_uri})
                        elif key == 'MONGODB_URI' and isinstance(value, str):
                            # Replace docker-compose service names in MongoDB URI
                            updated_uri = value.replace('mongodb://mongodb:', f'mongodb://{benchmark_id.lower()}-mongodb-service:')
                            env_vars.append({"name": key, "value": updated_uri})
                        elif key == 'MYSQL_HOST' and isinstance(value, str):
                            # Replace docker-compose service names for MySQL host
                            if value == 'db':
                                k8s_service_name = f"{benchmark_id.lower()}-db-service"
                                env_vars.append({"name": key, "value": k8s_service_name})
                            else:
                                k8s_service_name = f"{benchmark_id.lower()}-{value.replace('_', '-')}-service"
                                env_vars.append({"name": key, "value": k8s_service_name})
                        else:
                            env_vars.append({"name": key, "value": str(value)})
                elif isinstance(service_env, list):
                    for env_item in service_env:
                        if '=' in env_item:
                            key, value = env_item.split('=', 1)
                            # Map docker-compose service names to Kubernetes service names
                            if key == 'SERVER_HOSTNAME':
                                k8s_service_name = f"{benchmark_id.lower()}-{value.replace('_', '-')}-service"
                                env_vars.append({"name": key, "value": k8s_service_name})
                            elif key == 'MONGO_URI':
                                # Replace docker-compose service names in MongoDB URI
                                updated_uri = value.replace('mongodb://mongo:', f'mongodb://{benchmark_id.lower()}-mongo-service:')
                                env_vars.append({"name": key, "value": updated_uri})
                            elif key == 'MONGODB_URI':
                                # Replace docker-compose service names in MongoDB URI
                                updated_uri = value.replace('mongodb://mongodb:', f'mongodb://{benchmark_id.lower()}-mongodb-service:')
                                env_vars.append({"name": key, "value": updated_uri})
                            elif key == 'MYSQL_HOST':
                                # Replace docker-compose service names for MySQL host
                                if value == 'db':
                                    k8s_service_name = f"{benchmark_id.lower()}-db-service"
                                    env_vars.append({"name": key, "value": k8s_service_name})
                                else:
                                    k8s_service_name = f"{benchmark_id.lower()}-{value.replace('_', '-')}-service"
                                    env_vars.append({"name": key, "value": k8s_service_name})
                            else:
                                env_vars.append({"name": key, "value": value})
                        else:
                            env_vars.append({"name": env_item.split('=')[0], "value": env_item.split('=', 1)[1] if '=' in env_item else ""})
                            
        except Exception as e:
            print(f"Warning: Could not read reference compose for {benchmark_id}: {e}")
    
    # Add default environment variables for database services
    if is_db_service and db_image:
        if 'mongo' in db_image.lower():
            # MongoDB doesn't require authentication by default
            pass
        elif 'mysql' in db_image.lower():
            env_vars.extend([
                {"name": "MYSQL_ROOT_PASSWORD", "value": "rootpassword"},
                {"name": "MYSQL_DATABASE", "value": "testdb"},
                {"name": "MYSQL_USER", "value": "testuser"},
                {"name": "MYSQL_PASSWORD", "value": "testpass"}
            ])
        elif 'postgres' in db_image.lower():
            env_vars.extend([
                {"name": "POSTGRES_PASSWORD", "value": "postgres"},
                {"name": "POSTGRES_DB", "value": "testdb"}
            ])
    elif is_db_service and not db_image:
        # Handle database services that use custom builds
        if component == 'db' and benchmark_id == 'XBEN-025-24':
            env_vars.extend([
                {"name": "MYSQL_ROOT_PASSWORD", "value": "ssti_debug_art_gallery"},
                {"name": "MYSQL_DATABASE", "value": "art_db"}
            ])
        elif component in ['db', 'mysql'] or 'mysql' in component.lower():
            env_vars.extend([
                {"name": "MYSQL_ROOT_PASSWORD", "value": "rootpassword"},
                {"name": "MYSQL_DATABASE", "value": "testdb"},
                {"name": "MYSQL_USER", "value": "testuser"},
                {"name": "MYSQL_PASSWORD", "value": "testpass"}
            ])
    else:
        # For non-database components, check if they depend on database services
        # and add DB_HOST environment variable
        db_dependencies = get_database_dependencies(benchmark_id)
        if db_dependencies and not is_db_service:
            for db_service in db_dependencies:
                if db_service in ['db', 'mysql']:
                    env_vars.append({"name": "DB_HOST", "value": f"{benchmark_id.lower()}-{db_service}-service"})
                elif db_service in ['mongo', 'mongodb']:
                    env_vars.append({"name": "MONGO_HOST", "value": f"{benchmark_id.lower()}-{db_service}-service"})
        
        # Fallback for MySQL components that aren't detected as DB services
        if component in ['db', 'mysql'] or 'mysql' in component.lower():
            env_vars.extend([
                {"name": "MYSQL_ROOT_PASSWORD", "value": "rootpassword"},
                {"name": "MYSQL_DATABASE", "value": "testdb"},
                {"name": "MYSQL_USER", "value": "testuser"},
                {"name": "MYSQL_PASSWORD", "value": "testpass"}
            ])
    
    container_spec = {
        "name": component.replace("_", "-"),
        "image": image_name,
        "imagePullPolicy": "Always",
        "ports": [{"containerPort": port, "protocol": "TCP"}],
        "env": env_vars
    }
    
    # Add health checks with the correct port
    container_spec["livenessProbe"] = {
        "tcpSocket": {
            "port": port
        },
        "initialDelaySeconds": 30,
        "periodSeconds": 10,
        "timeoutSeconds": 5,
        "failureThreshold": 5
    }
    container_spec["readinessProbe"] = {
        "tcpSocket": {
            "port": port
        },
        "initialDelaySeconds": 10,
        "periodSeconds": 5,
        "timeoutSeconds": 5,
        "failureThreshold": 3
    }
    
    return container_spec

def create_deployment_manifest(benchmark_id, components):
    """Create deployment manifest for a benchmark."""
    # Create separate deployments for each component to ensure proper scaling
    deployments = []
    
    for component in components:
        container_spec = create_container_spec(benchmark_id, component)
        
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"{benchmark_id.lower()}-{component.replace('_', '-')}-deployment",
                "namespace": NAMESPACE,
                "labels": {
                    "app": benchmark_id.lower(),
                    "benchmark": benchmark_id,
                    "component": component.replace('_', '-')
                }
            },
            "spec": {
                "replicas": 1,  # Each component gets its own deployment with 1 replica
                "selector": {
                    "matchLabels": {
                        "app": benchmark_id.lower(),
                        "component": component.replace('_', '-')
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": benchmark_id.lower(),
                            "benchmark": benchmark_id,
                            "component": component.replace('_', '-')
                        }
                    },
                    "spec": {
                        "containers": [container_spec],
                        "restartPolicy": "Always"
                    }
                }
            }
        }
        deployments.append(deployment)
    
    return deployments

def create_service_manifest(benchmark_id, components):
    """Create service manifest for a benchmark."""
    services = []
    
    for component in components:
        # Get the correct port from the Dockerfile
        port = get_port_from_dockerfile(benchmark_id, component)
            
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"{benchmark_id.lower()}-{component.replace('_', '-')}-service",
                "namespace": NAMESPACE,
                "labels": {
                    "app": benchmark_id.lower(),
                    "benchmark": benchmark_id,
                    "component": component.replace('_', '-')
                }
            },
            "spec": {
                "selector": {
                    "app": benchmark_id.lower(),
                    "component": component.replace('_', '-')
                },
                "ports": [{"name": f"{component.replace('_', '-')}-port", "port": port, "targetPort": port}],
                "type": "ClusterIP"
            }
        }
        services.append(service)
    
    return services

def create_secret_manifest(benchmark_id):
    """Create secret manifest for benchmark flag."""
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{benchmark_id.lower()}-flag",
            "namespace": NAMESPACE
        },
        "type": "Opaque",
        "data": {
            "flag": "ZmxhZ3t0ZXN0X2ZsYWd9"  # base64 encoded "flag{test_flag}"
        }
    }
    
    return secret

def main():
    """Generate all deployment manifests."""
    print(f"DEBUG: Using namespace: {NAMESPACE}")
    all_manifests = []
    
    # Generate manifests for all 104 benchmarks
    for i in range(1, 105):
        benchmark_id = f"XBEN-{i:03d}-24"
        components = get_benchmark_components(benchmark_id)
        
        if not components:
            print(f"Warning: No components found for {benchmark_id}")
            continue
        
        print(f"Generating manifests for {benchmark_id} with components: {components}")
        
        # Create deployments (one per component)
        deployments = create_deployment_manifest(benchmark_id, components)
        all_manifests.extend(deployments)
        
        # Create services (one per component)
        services = create_service_manifest(benchmark_id, components)
        all_manifests.extend(services)
        
        # Create secret
        secret = create_secret_manifest(benchmark_id)
        all_manifests.append(secret)
    
    # Write all manifests to file
    with open("all-benchmarks-corrected.yaml", "w") as f:
        for i, manifest in enumerate(all_manifests):
            if i > 0:
                f.write("---\n")
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
    
    print(f"Generated {len(all_manifests)} manifests for all benchmarks")
    print("Output written to: all-benchmarks-corrected.yaml")

if __name__ == "__main__":
    main()