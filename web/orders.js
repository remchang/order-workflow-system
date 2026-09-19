/* ============================================================
   物资领用工作台前端
   同源调用 Node-RED 暴露的 /api/*，不跨域。

   两条纪律：
     ① 库存只显示服务端返回的值，页面**绝不做本地扣减**。
        页面自己算库存，刷新一下就露馅，那种界面是假的。
     ② 所有来自接口的文本都转义后再插入 DOM，不拼 innerHTML。
   ============================================================ */

var shangpinBiao = [];

/* ---------------- 小工具 ---------------- */

function zhuanYi(wen) {
  if (wen === null || wen === undefined) return "";
  return String(wen)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function tishi(wen) {
  var k = document.getElementById("tishilan");
  k.textContent = wen;
  k.hidden = false;
  clearTimeout(k._t);
  k._t = setTimeout(function () { k.hidden = true; }, 2400);
}

function geshihua(iso) {
  if (!iso) return "—";
  var d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  var b = function (n) { return n < 10 ? "0" + n : "" + n; };
  return d.getFullYear() + "-" + b(d.getMonth() + 1) + "-" + b(d.getDate())
    + " " + b(d.getHours()) + ":" + b(d.getMinutes()) + ":" + b(d.getSeconds());
}

async function diao(lujing, xuan) {
  var x;
  try {
    x = await fetch(lujing, xuan || {});
  } catch (e) {
    // 网络层就失败了：这种情况结果未知，不能断言服务端没执行
    var cuo = new Error("连不上服务：" + e.message);
    cuo.lei_xing = "wangluo";
    throw cuo;
  }
  var ti = null;
  try { ti = await x.json(); } catch (e2) { ti = null; }

  if (!x.ok) {
    var c2 = new Error((ti && ti.xiaoxi) || ("请求失败 HTTP " + x.status));
    c2.zhuangtai = x.status;
    c2.lei_xing = (ti && ti.lei_xing) || "";
    c2.jiaoyi = (ti && ti.jiaoyi) || "";
    c2.baoti = ti;
    throw c2;
  }
  return ti;
}

/* ---------------- 健康灯 ---------------- */

async function shuaxinDeng() {
  var d1 = document.getElementById("deng-flow");
  var d2 = document.getElementById("deng-kucun");
  try {
    await diao("/health");
    d1.className = "deng hao";
    d1.textContent = "流程正常";
  } catch (e) {
    d1.className = "deng huai";
    d1.textContent = "流程异常";
  }
  try {
    var t = await diao("/api/products");
    d2.className = "deng hao";
    d2.textContent = "库存服务正常";
  } catch (e2) {
    d2.className = "deng huai";
    d2.textContent = "库存服务异常";
  }
}

/* ---------------- 商品 ---------------- */

function tianchongShangpin(mingdan) {
  shangpinBiao = mingdan;
  var xuan = document.getElementById("sku");
  var dangqian = xuan.value;
  var hang = [];
  for (var i = 0; i < mingdan.length; i++) {
    var s = mingdan[i];
    hang.push('<option value="' + zhuanYi(s.sku) + '">'
      + zhuanYi(s.sku + "　" + s.mingcheng) + "</option>");
  }
  xuan.innerHTML = hang.join("");
  if (dangqian) xuan.value = dangqian;
  shuaxinKucun();

  var tbody = document.getElementById("shangpin-ti");
  var h2 = [];
  for (var j = 0; j < mingdan.length; j++) {
    var p = mingdan[j];
    var lei = p.kucun === 0 ? "wu" : (p.kucun <= 5 ? "jin" : "duo");
    h2.push("<tr>"
      + "<td class='bianhao'>" + zhuanYi(p.sku) + "</td>"
      + "<td>" + zhuanYi(p.mingcheng) + "</td>"
      + "<td>" + zhuanYi(p.leibie) + "</td>"
      + "<td class='" + lei + "'>" + p.kucun + "</td>"
      + "<td>¥" + Number(p.danjia).toFixed(2) + "</td>"
      + "<td>" + zhuanYi(p.danwei) + "</td>"
      + "</tr>");
  }
  tbody.innerHTML = h2.join("");
}

function shuaxinKucun() {
  var sku = document.getElementById("sku").value;
  var kuang = document.getElementById("kucun-xianshi");
  for (var i = 0; i < shangpinBiao.length; i++) {
    if (shangpinBiao[i].sku === sku) {
      kuang.textContent = shangpinBiao[i].kucun + " " + shangpinBiao[i].danwei;
      if (shangpinBiao[i].kucun === 0) { kuang.style.color = "#dc2626"; }
      else { kuang.style.color = "#0f766e"; }
      return;
    }
  }
  kuang.textContent = "—";
}

async function jiazaiShangpin() {
  try {
    var ti = await diao("/api/products");
    tianchongShangpin(ti.products || []);
  } catch (e) {
    document.getElementById("shangpin-ti").innerHTML =
      '<tr><td colspan="6" class="kong">读取商品失败：' + zhuanYi(e.message) + "</td></tr>";
  }
}

/* ---------------- 提交 ---------------- */

function xianshiJieguo(ti) {
  var k = document.getElementById("jieguo");
  k.hidden = false;
  k.className = "jieguo" + (ti.chongfu ? " chongfu" : "");
  var hang = [];
  hang.push("<dt>请求编号</dt><dd>" + zhuanYi(ti.request_id) + "</dd>");
  hang.push("<dt>商品</dt><dd>" + zhuanYi(ti.sku) + "</dd>");
  hang.push("<dt>数量</dt><dd>" + zhuanYi(ti.quantity) + "</dd>");
  hang.push("<dt>剩余库存</dt><dd>" + zhuanYi(ti.shengyu) + "</dd>");
  hang.push("<dt>状态</dt><dd>" + zhuanYi(ti.zhuangtai) + "</dd>");
  hang.push("<dt>规则版本</dt><dd>" + zhuanYi(ti.guize_banben || "—") + "</dd>");
  hang.push("<dt>说明</dt><dd>" + zhuanYi(ti.xiaoxi) + "</dd>");
  k.innerHTML = "<dl>" + hang.join("") + "</dl>";
}

function xianshiCuowu(e) {
  var k = document.getElementById("cuowu");
  k.hidden = false;
  var lei = "";
  if (e.zhuangtai === 409) lei = "［业务拒绝 409］";
  else if (e.zhuangtai === 400) lei = "［请求有问题 400］";
  else if (e.zhuangtai === 404) lei = "［找不到 404］";
  else if (e.zhuangtai === 502) lei = "［依赖失败 502］";
  var html = lei + zhuanYi(e.message);
  if (e.jiaoyi) {
    html += '<span class="jiaoyi">建议：' + zhuanYi(e.jiaoyi) + "</span>";
  }
  k.innerHTML = html;
}

async function tijiao(shijian) {
  if (shijian) shijian.preventDefault();

  var anniu = document.getElementById("anniu-tijiao");
  var jindu = document.getElementById("jindu");
  var bianhao = document.getElementById("request_id").value.trim();
  var sku = document.getElementById("sku").value;
  var shuliang = parseInt(document.getElementById("quantity").value, 10);

  document.getElementById("jieguo").hidden = true;
  document.getElementById("cuowu").hidden = true;

  // 前端只做最便宜的检查，真正的把关在流程和库存服务里
  if (!bianhao) { alert("请填请求编号"); return; }
  if (!/^[A-Za-z0-9_-]{4,40}$/.test(bianhao)) {
    alert("编号要 4~40 位字母数字或 - _"); return;
  }
  if (!Number.isInteger(shuliang) || shuliang <= 0) { alert("数量要是正整数"); return; }
  if (shuliang > 20) { alert("单次最多 20 件"); return; }

  // 防重复点击。但记住：这只是体验优化，
  // 真正的不重复扣减靠服务端的 request_id 唯一约束 + 事务。
  anniu.disabled = true;
  jindu.textContent = "提交中…";

  try {
    var ti = await diao("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: bianhao, sku: sku, quantity: shuliang })
    });
    xianshiJieguo(ti);
    tishi(ti.chongfu ? "幂等命中，未重复扣减" : "提交成功");
    await jiazaiShangpin();
    await shuaxinLiebiao();
    document.getElementById("request_id").value = "";
  } catch (e) {
    xianshiCuowu(e);
  } finally {
    anniu.disabled = false;
    jindu.textContent = "";
  }
}

/* ---------------- 记录列表 ---------------- */

async function shuaxinLiebiao() {
  var tbody = document.getElementById("liebiao-ti");
  var zt = document.getElementById("shaixuan").value;
  var lujing = "/api/orders" + (zt ? ("?zhuangtai=" + encodeURIComponent(zt)) : "");
  try {
    var ti = await diao(lujing);
    var hang = ti.reservations || [];
    if (!hang.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="kong">还没有记录</td></tr>';
      return;
    }
    var h = [];
    for (var i = 0; i < hang.length; i++) {
      var r = hang[i];
      var lei = r.shengyu === 0 ? "wu" : (r.shengyu <= 5 ? "jin" : "duo");
      h.push("<tr>"
        + "<td class='bianhao'>" + zhuanYi(r.request_id) + "</td>"
        + "<td>" + zhuanYi(r.sku) + "</td>"
        + "<td>" + r.quantity + "</td>"
        + "<td class='" + lei + "'>" + r.shengyu + "</td>"
        + "<td>" + zhuanYi(r.zhuangtai) + "</td>"
        + "<td>" + zhuanYi(r.guize_banben || "—") + "</td>"
        + "<td>" + geshihua(r.chuangjian_shijian) + "</td>"
        + "<td><button class='xiao' onclick=\"kanXiangqing('"
          + zhuanYi(r.request_id) + "')\">详情</button></td>"
        + "</tr>");
    }
    tbody.innerHTML = h.join("");
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="8" class="kong">加载失败：'
      + zhuanYi(e.message) + "</td></tr>";
  }
}

async function kanXiangqing(bianhao) {
  var kuang = document.getElementById("chouti-neirong");
  document.getElementById("chouti-biaoti").textContent = "记录 " + bianhao;
  kuang.innerHTML = "<dt>读取中</dt><dd>…</dd>";
  document.getElementById("zhezhao").hidden = false;
  try {
    var ti = await diao("/api/orders/" + encodeURIComponent(bianhao));
    var r = ti.reservation;
    var hang = [];
    var zi = {
      "请求编号": r.request_id, "商品": r.sku, "数量": r.quantity,
      "剩余库存": r.shengyu, "状态": r.zhuangtai,
      "规则版本": r.guize_banben, "创建时间": geshihua(r.chuangjian_shijian)
    };
    for (var k in zi) {
      if (Object.prototype.hasOwnProperty.call(zi, k)) {
        hang.push("<dt>" + zhuanYi(k) + "</dt><dd>" + zhuanYi(zi[k]) + "</dd>");
      }
    }
    kuang.innerHTML = hang.join("");
  } catch (e) {
    kuang.innerHTML = "<dt>出错</dt><dd>" + zhuanYi(e.message) + "</dd>";
  }
}

/* ---------------- 初始化 ---------------- */

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("biaodan").addEventListener("submit", tijiao);
  document.getElementById("sku").addEventListener("change", shuaxinKucun);
  document.getElementById("anniu-shuaxin").addEventListener("click", function () {
    jiazaiShangpin(); shuaxinLiebiao(); shuaxinDeng();
  });
  document.getElementById("shaixuan").addEventListener("change", shuaxinLiebiao);
  document.getElementById("guan-chouti").addEventListener("click", function () {
    document.getElementById("zhezhao").hidden = true;
  });
  document.getElementById("zhezhao").addEventListener("click", function (e) {
    if (e.target.id === "zhezhao") document.getElementById("zhezhao").hidden = true;
  });

  jiazaiShangpin();
  shuaxinLiebiao();
  shuaxinDeng();
  setInterval(shuaxinDeng, 30000);
});
