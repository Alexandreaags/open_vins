from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    LogInfo,
    OpaqueFunction,
    ExecuteProcess,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

launch_args = [
    DeclareLaunchArgument(
        name="config",
        default_value="bus_dataset",
        description="pasta de config do OpenVINS (em ov_msckf/config/<nome>)",
    ),
    DeclareLaunchArgument(
        name="bag_path",
        default_value="/home/alexandre/tcc_ws/src/stereo-vi-underwater-dataset/ros2_bags/bus_outside.db3",
        description="caminho completo do bag a reproduzir",
    ),
    DeclareLaunchArgument(
        name="glare_masker_path",
        default_value="/home/alexandre/tcc_ws/src/glare_masker/glare_masker.py",
        description="caminho completo do script glare_masker.py",
    ),
    DeclareLaunchArgument(
        name="rviz_enable", default_value="true", description="abrir o RViz2"
    ),
    DeclareLaunchArgument(
        name="bag_delay",
        default_value="3.0",
        description="segundos de espera antes de iniciar o bag, para dar tempo dos outros nós subirem",
    ),
]


def launch_setup(context):
    config = LaunchConfiguration("config").perform(context)
    configs_dir = os.path.join(get_package_share_directory("ov_msckf"), "config")
    available_configs = os.listdir(configs_dir)

    if config not in available_configs:
        return [
            LogInfo(
                msg="ERROR: unknown config: '{}' - Available configs are: {} - not starting OpenVINS".format(
                    config, ", ".join(available_configs)
                )
            )
        ]

    config_path = os.path.join(configs_dir, config, "estimator_config.yaml")
    bag_path = LaunchConfiguration("bag_path").perform(context)
    glare_masker_path = LaunchConfiguration("glare_masker_path").perform(context)
    bag_delay = float(LaunchConfiguration("bag_delay").perform(context))

    # --- republisher da câmera 1 (compressed -> raw) ---
    republish_cam0 = ExecuteProcess(
        cmd=[
            "ros2", "run", "image_transport", "republish", "compressed", "raw",
            "--ros-args",
            "--remap", "in/compressed:=/slave1/image_raw/compressed",
            "--remap", "out:=/slave1/image_raw",
        ],
        output="screen",
    )

    # --- republisher da câmera 2 (compressed -> raw) ---
    republish_cam1 = ExecuteProcess(
        cmd=[
            "ros2", "run", "image_transport", "republish", "compressed", "raw",
            "--ros-args",
            "--remap", "in/compressed:=/slave2/image_raw/compressed",
            "--remap", "out:=/slave2/image_raw",
        ],
        output="screen",
    )

    # --- nó de mascaramento de glare (script solto, não é pacote ROS2) ---
    # glare_masker = ExecuteProcess(
    #     cmd=["python3", glare_masker_path],
    #     output="screen",
    # )

    # --- OpenVINS ---
    openvins_node = Node(
        package="ov_msckf",
        executable="run_subscribe_msckf",
        namespace="ov_msckf",
        output="screen",
        parameters=[
            {"verbosity": "INFO"},
            {"use_stereo": True},
            {"max_cameras": 2},
            {"save_total_state": False},
            {"config_path": config_path},
            {"use_sim_time": True},
        ],
    )

    # --- RViz2 ---
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        condition=IfCondition(LaunchConfiguration("rviz_enable")),
        arguments=[
            "-d",
            os.path.join(
                get_package_share_directory("ov_msckf"), "launch", "display_ros2.rviz"
            ),
            "--ros-args",
            "--log-level",
            "warn",
        ],
        parameters=[{"use_sim_time": True}],
    )

    # --- bag: atrasado propositalmente, para os outros nós já estarem
    #     com suas subscriptions registradas antes das mensagens começarem
    bag_play = TimerAction(
        period=bag_delay,
        actions=[
            ExecuteProcess(
                cmd=["ros2", "bag", "play", bag_path, "--clock"],
                output="screen",
            )
        ],
    )

    return [
        republish_cam0,
        republish_cam1,
        # glare_masker,
        openvins_node,
        rviz_node,
        bag_play,
    ]


def generate_launch_description():
    opfunc = OpaqueFunction(function=launch_setup)
    ld = LaunchDescription(launch_args)
    ld.add_action(opfunc)
    return ld