const status=document.getElementById('status'),button=document.getElementById('capture');
button.textContent='Kiểm tra kết nối';
async function check(){
  try{
    const result=await chrome.runtime.sendMessage({kind:'status'});
    const labels={CONNECTED:'Đã kết nối. Chỉ đọc trang ứng dụng yêu cầu.',OFF:'Đang TẮT. Bật Kết nối ToonCN trong ứng dụng.',
      WAITING_APP:'Đang chờ ứng dụng.',READING_REQUESTED_PAGE:'Đang đọc trang ToonCN được ứng dụng yêu cầu.',
      NATIVE_HOST_UNAVAILABLE:'[NATIVE_HOST_UNAVAILABLE] Không mở được native host. Kiểm tra register_host.bat.'};
    status.textContent=labels[result.state]||'Đang nối native host…';
  }catch{status.textContent='[BRIDGE_FAILED] Hãy Reload extension tại chrome://extensions.';}
}
button.addEventListener('click',check);void check();
