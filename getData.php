<?php
$servername = "localhost";
$username = "USERNAME";
$password = "PASSWORD";
$dbname = "Monitoring";

$rows = array();
$table = array();
$table['cols'] = array(
    // Labels for your chart, these represent the column titles
    array('label' => 'Date and Time', 'type' => 'number'),
    array('label' => 'Temperature', 'type' => 'number'),
    array('label' => 'Humidity', 'type' => 'number')
); 

// Create connection
//$conn = new mysqli($servername, $username, $password, $dbname);
$conn = mysqli_connect($servername, $username, $password, $dbname);
// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

$sql = "SELECT ComputerTime, Temperature, Humidity from TempHumid ORDER BY id DESC LIMIT 360";
$result = mysqli_query($conn,$sql);

//if ($result->num_rows > 0) {
    // output data of each row
    while($row = mysqli_fetch_array($result)) {
       $temp = array();
//       $datetime = date('d/m/Y H:i', $row[0]);
//       $temp[] = array('v' => $datetime); 
       $temp[] = array('v' => $row[0]); 
       $temp[] = array('v' => $row[1]); 
       $temp[] = array('v' => $row[2]); 
       $rows[] = array('c' => $temp); 
    }
//} else {
//    echo "No current temperature  - ERROR?";
//}
$table['rows'] = $rows;
header('Content-type: application/json');
echo json_encode($table);
$conn->close();
?>
