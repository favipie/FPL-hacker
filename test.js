async function test() {
  try {
    console.log("Fetching...");

    const res = await fetch('http://localhost:3001/api/bootstrap');
    const data = await res.json();

    console.log("Players:", data.elements.length);
    console.log("First Player:", data.elements[0]);

  } catch (err) {
    console.error("Error:", err);
  }
}

test();