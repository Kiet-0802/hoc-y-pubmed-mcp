# Triển khai lên Render (ví dụ)

Đây KHÔNG phải ZIP để upload vào OpenAI Plugin Directory. Đây là máy chủ phải deploy riêng.

1. Đưa các file trong `hoc-y-mcp-server/` lên một repo GitHub của bạn (đặt `render.yaml` ở repo root).
2. Trên https://dashboard.render.com/ chọn New > Blueprint và kết nối repo để deploy web service. Xem giá dịch vụ/trạng thái luôn bật trước khi chọn gói.
3. Sau khi deploy, xác nhận `https://<render-host>/healthz` trả `{"status":"ok"` và MCP Inspector kết nối thành công tới `https://<render-host>/mcp`.
4. Mở `mcp.json` trong `skill.zip`, thay placeholder URL bằng host vừa deploy; nén lại plugin.
5. Trong OpenAI Plugins chọn With MCP > Upload, rồi MCPs > Connect. Khi được hỏi domain challenge, đặt `OPENAI_APPS_CHALLENGE_TOKEN` đúng như OpenAI cấp; redeploy/restart rồi kiểm tra endpoint `.well-known/openai-apps-challenge` chỉ trả token.

Không gửi dữ liệu bệnh nhân. Triển khai thật cần hạn chế lưu lượng, xử lý lỗi, HTTPS, kiểm tra pháp lý sử dụng NCBI, reviewer testing.
