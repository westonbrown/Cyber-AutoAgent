<?php
    $conn = new mysqli($_ENV['DB_HOST'] ?? 'db', $_ENV['MYSQL_USER'] ?? 'user', $_ENV['MYSQL_PASSWORD'] ?? 'password', $_ENV['MYSQL_DATABASE'] ?? 'blogDB');
    if ($conn->connect_error) {
        die("Connection failed: " . $conn->connect_error);
    }
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Home</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="container">
    <h1>Welcome to Our Blog</h1>


    <form action="" method="GET">
        <label for="category">Choose a category:</label>
        <select name="category" id="category" onchange="this.form.submit()">
            <option value="">All Categories</option>        
            <?php
            $cat_result = $conn->query("SELECT DISTINCT category FROM posts");
            while ($row = $cat_result->fetch_assoc()) {
                $selected = ($row['category'] == $category) ? 'selected' : '';
                echo "<option value='{$row['category']}' {$selected}>{$row['category']}</option>";
            }
            ?>
        </select>
    </form>

    <?php

    $unescaped_category = isset($_GET['category']) ? $_GET['category'] : '';

    if (!empty($unescaped_category)) {
        // Verify category exists
        // Injection point
        $result = $conn->query("SELECT DISTINCT category FROM posts where category = '" . $unescaped_category    ."'");

        if ($result === false) {
            die("Error in query: " . $conn->error);
        }
        if ($result->num_rows == 0) {
            die("Category does not  exist");
        }
    }

    // Filter posts
    $category = mysqli_real_escape_string($conn, $unescaped_category);
    $sql = "SELECT * FROM posts WHERE published = 1 ";

    if (!empty($category)) {
        $sql .= "and category = '" . $category . "' ";
    }
    $sql .= "ORDER BY created_at DESC";

    $result = $conn->query($sql);

    if ($result === false) {
        die("Error in query: " . $conn->error);
    }

    if ($result->num_rows > 0) {
        while($row = $result->fetch_assoc()) {
            echo "<div class='post'>
                    <h2>{$row['title']}</h2>
                    <p>Category: {$row['category']}</p>
                    <img src='images/{$row['image']}' alt='{$row['title']}' style='width:200px;height:200px;'/>
                    <p>" . substr($row['content'], 0, 200) . "...</p>
                </div>";
        }
    } else {
        echo "<p>No posts found.</p>";
    }
    $conn->close();
    ?>
</div>
<a href="admin.php">Admin Login</a>
</body>
</html>
