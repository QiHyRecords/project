document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const errorMsg = document.getElementById("error-msg");
  errorMsg.textContent = "";

  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      const err = await res.json();
      errorMsg.textContent = err.detail || "Đăng nhập thất bại";
      return;
    }
    const data = await res.json();
    localStorage.setItem("aas_token", data.access_token);
    localStorage.setItem("aas_role", data.role);
    localStorage.setItem("aas_username", data.username);
    window.location.href = "/index.html";
  } catch (err) {
    errorMsg.textContent = "Không thể kết nối tới server";
  }
});
