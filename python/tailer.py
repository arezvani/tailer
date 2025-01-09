import threading
import time
import subprocess
import json
import argparse

# Global variables
namespace = ""
output_file = ""
exclude_containers = []
exclude_pods = []
watch_interval = 5  # seconds
retry_interval = 7200  # 2 hours (in seconds)
processed_pods = {}
lock = threading.Lock()


def get_pods():
    """Fetch all pods in the namespace."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error fetching pods: {result.stderr}")
            return []
        pods = json.loads(result.stdout).get("items", [])
        return pods
    except Exception as e:
        print(f"Error in get_pods: {e}")
        return []


def get_pod_phase(pod):
    """Get the phase of a pod."""
    return pod.get("status", {}).get("phase", "Unknown")


def get_containers(pod):
    """Get the list of containers in a pod."""
    containers = pod.get("spec", {}).get("containers", [])
    return [container["name"] for container in containers]


def log_container(pod_name, container_name):
    """Log container logs to the output file."""
    if container_name in exclude_containers:
        print(f"Skipping excluded container: {container_name}")
        return

    print(f"  Tailing logs for container: {container_name}")

    try:
        command = ["kubectl", "logs", "-f", pod_name, "-c", container_name, "-n", namespace, "--tail", "0"]
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout:
                with open(output_file, "a") as f:
                    f.write(f"{namespace}/{pod_name}[{container_name}]: {line}")
    except Exception as e:
        print(f"Error logging container {pod_name}/{container_name}: {e}")


def process_new_pods():
    """Thread function to track and process new pods."""
    global processed_pods

    while True:
        pods = get_pods()

        # Collect current pod names
        current_pod_names = set(pod["metadata"]["name"] for pod in pods)

        # Remove deleted pods from processed_pods
        with lock:
            for pod_name in list(processed_pods.keys()):
                if pod_name not in current_pod_names:
                    del processed_pods[pod_name]

        for pod in pods:
            pod_name = pod["metadata"]["name"]

            if pod_name in exclude_pods:
                print(f"Skipping excluded pod: {pod_name}")
                continue

            with lock:
                if pod_name in processed_pods:
                    continue

            pod_phase = get_pod_phase(pod)
            if pod_phase not in ["Running", "Succeeded", "Failed"]:
                continue

            print(f"Processing new pod: {pod_name}")
            containers = get_containers(pod)

            for container_name in containers:
                threading.Thread(target=log_container, args=(pod_name, container_name), daemon=True).start()

            with lock:
                processed_pods[pod_name] = True

        time.sleep(watch_interval)


def refresh_logs():
    """Refresh logs every retry_interval to avoid missing logs."""
    global processed_pods

    while True:
        time.sleep(retry_interval)
        print("Refreshing logs...")
        with lock:
            processed_pods = {}


def main():
    global namespace, output_file, exclude_containers, exclude_pods

    # Parse arguments
    parser = argparse.ArgumentParser(description="Track and log Kubernetes pod containers.")
    parser.add_argument("-n", "--namespace", required=True, help="Kubernetes namespace")
    parser.add_argument("-o", "--output-file", required=True, help="Output file for logs")
    parser.add_argument("--exclude-containers", default="", help="Comma-separated list of containers to exclude")
    parser.add_argument("--exclude-pods", default="", help="Comma-separated list of pods to exclude")

    args = parser.parse_args()

    namespace = args.namespace
    output_file = args.output_file
    exclude_containers = args.exclude_containers.split(",") if args.exclude_containers else []
    exclude_pods = args.exclude_pods.split(",") if args.exclude_pods else []

    # Start threads
    threading.Thread(target=process_new_pods, daemon=True).start()
    threading.Thread(target=refresh_logs, daemon=True).start()

    # Keep the main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
