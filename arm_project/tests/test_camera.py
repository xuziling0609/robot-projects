import pytest
from unittest.mock import MagicMock
from src.vision.camera import RealSenseCamera

@pytest.fixture(autouse=True)
def mock_cam_config(mocker):
    mocker.patch('src.vision.camera.get_config', return_value={
        'vision': {
            'camera': {
                'color_width': 1280,
                'color_height': 720,
                'depth_width': 848,
                'depth_height': 480,
                'fps': 30
            }
        }
    })

def test_camera_start_success(mocker):
    mock_rs = mocker.patch('src.vision.camera.rs')
    mock_pipeline = MagicMock()
    mock_rs.pipeline.return_value = mock_pipeline
    
    mock_profile = MagicMock()
    mock_pipeline.start.return_value = mock_profile
    
    # Mock depth sensor
    mock_sensor = MagicMock()
    mock_sensor.get_depth_scale.return_value = 0.001
    mock_profile.get_device().first_depth_sensor.return_value = mock_sensor
    
    cam = RealSenseCamera()
    success = cam.start()
    
    assert success is True
    assert cam.is_running is True
    assert cam.depth_scale == 0.001
    assert mock_pipeline.wait_for_frames.call_count == 10

def test_camera_start_no_device(mocker):
    mock_rs = mocker.patch('src.vision.camera.rs')
    mock_pipeline = MagicMock()
    mock_pipeline.start.side_effect = RuntimeError("No device connected")
    mock_rs.pipeline.return_value = mock_pipeline
    
    cam = RealSenseCamera()
    mocker.patch.object(cam, 'reset_realsense_hardware', return_value=True)
    success = cam.start()
    
    assert success is False
    assert cam.is_running is False
    assert cam.pipeline is None
    cam.reset_realsense_hardware.assert_called_once()

def test_camera_start_recovers_on_retry(mocker):
    mock_rs = mocker.patch('src.vision.camera.rs')
    mock_pipeline = MagicMock()
    # 第一次报错 No device connected，第二次成功
    mock_profile = MagicMock()
    mock_sensor = MagicMock()
    mock_sensor.get_depth_scale.return_value = 0.001
    mock_profile.get_device().first_depth_sensor.return_value = mock_sensor
    mock_pipeline.start.side_effect = [RuntimeError("No device connected"), mock_profile]
    mock_rs.pipeline.return_value = mock_pipeline
    
    cam = RealSenseCamera()
    mocker.patch.object(cam, 'reset_realsense_hardware', return_value=True)
    success = cam.start()
    
    assert success is True
    assert cam.is_running is True
    cam.reset_realsense_hardware.assert_called_once()

def test_camera_get_frames_when_stopped():
    cam = RealSenseCamera()
    cam.is_running = False
    
    d, c, raw = cam.get_frames()
    assert d is None
    assert c is None
    assert raw is None

def test_camera_get_frames_disconnect_resets_state(mocker):
    mock_rs = mocker.patch('src.vision.camera.rs')
    mock_pipeline = MagicMock()
    mock_pipeline.wait_for_frames.side_effect = RuntimeError("wait_for_frames cannot be called before start()")
    
    cam = RealSenseCamera()
    cam.pipeline = mock_pipeline
    cam.is_running = True
    
    d, c, raw = cam.get_frames()
    assert d is None
    assert c is None
    assert raw is None
    assert cam.is_running is False
    assert cam.pipeline is None

def test_camera_reconnect(mocker):
    cam = RealSenseCamera()
    mocker.patch.object(cam, 'start', return_value=True)
    
    res = cam.reconnect()
    assert res is True
