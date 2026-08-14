<?php
$servername = "localhost";
$username = "USERNAME";
$password = "PASSWORD";
$dbname = "Monitoring";

$table = array();
$table['cols'] = array(
    array('label' => 'Date and Time', 'type' => 'number'),
    array('label' => 'Temperature', 'type' => 'number'),
    array('label' => 'Humidity', 'type' => 'number')
);

$conn = mysqli_connect($servername, $username, $password, $dbname);
if (!$conn) {
    header('HTTP/1.1 500 Internal Server Error');
    header('Content-type: application/json');
    echo json_encode(array('error' => 'Connection failed: ' . mysqli_connect_error()));
    exit;
}

$sql = "SELECT ComputerTime, Temperature, Humidity FROM ("
     . "SELECT ComputerTime, Temperature, Humidity FROM TempHumid "
     . "ORDER BY id DESC LIMIT 360"
     . ") AS recent ORDER BY ComputerTime ASC";
$result = mysqli_query($conn, $sql);

$rows = array();
if ($result) {
    while ($row = mysqli_fetch_array($result)) {
        $temp = array();
        $temp[] = array('v' => (float)$row[0]);
        $temp[] = array('v' => (float)$row[1]);
        $temp[] = array('v' => (float)$row[2]);
        $rows[] = array('c' => $temp);
    }
    mysqli_free_result($result);
} else {
    header('HTTP/1.1 500 Internal Server Error');
    header('Content-type: application/json');
    echo json_encode(array('error' => 'Query failed: ' . mysqli_error($conn)));
    mysqli_close($conn);
    exit;
}

$table['rows'] = $rows;
header('Content-type: application/json');
echo json_encode($table);
mysqli_close($conn);
?>
