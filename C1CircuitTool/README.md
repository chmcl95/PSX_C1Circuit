# C1CircuitTool

C1 Circuit (SLPS-00279) の `.S` アーカイブを扱うコマンドラインツール。

```
C1CircuitTool <verb> -i <input> [-o <output>]
```

| verb | 用途 |
|---|---|
| `unpack` | 任意の `.S` を `00000000.BIN`, `00000001.BIN` ... に展開 |
| `pack` | フォルダ内のファイルを `.S` に再構築（**ファイル名昇順**） |
| `rcardt-unpack` | 車の `.S` を編集用フォルダに展開（モデル + TIM + プリセット） |
| `rcardt-pack` | 編集用フォルダから車の `.S` を再構築 |

---

## LZSS0 デコーダの修正（v1.02）

**`unpack` が2番目以降のファイルを黙って壊す不具合を修正しました。**

原因は LZSS の辞書初期化規約の相違です。ゲーム（および QuickBMS の
`comType LZSS0`）は Okumura式の「4096バイトのリングバッファを 0x00 で埋め、
書き込みカーソルを N-F = 4078 から開始する」規約ですが、
`AuroraLib.Compression 2.0.0` はこれと異なる挙動をします。

圧縮データが**初期辞書（＝ゼロ領域）を参照している箇所だけ**が壊れるため、
初期辞書をほぼ参照しないモデル（`00000000.BIN`）は正常に見え、
参照するテクスチャ（`00000001.BIN`）が壊れる、という症状になっていました。
市販版17アーカイブのうち **16のテクスチャが影響を受けていました**。

ゲーム互換のデコーダ (`Lzss0.cs`) に差し替え、17アーカイブ全てが
QuickBMS の出力とバイト単位で一致することを確認済みです。
**QuickBMS を併用する必要はなくなりました。**

なお圧縮側 (`pack`) は影響を受けていなかったため、`AuroraLib` のまま
使用しています（圧縮結果をゲーム互換デコーダで展開して検証済み）。

---

## rcardt-unpack

```
C1CircuitTool rcardt-unpack -i NA8C.S -o work/NA8C
```

車の `.S`（モデル + テクスチャの2ファイル）を編集しやすい形に展開します。

```
work/NA8C/
├── 00000000.BIN            モデル（Blenderアドオンでインポート）
├── 000_body_256x64.TIM     テクスチャ（ps-image 等で編集）
├── 001_body_96x48.TIM
├── 003_shadow_8x8.TIM
├── 004_tire_8x8.TIM
│   ...
└── clut_presets.json       CLUTスロット定義
```

`00000001.BIN` の中身は「パレットブロック + ピクセルブロック」のペアが
並んだ形式で、これは Sony TIM のデータセクションと**長さフィールドの
数え方（±12）だけが違う**ものです。そのため各ペアを TIM 1ファイルに変換でき、
ps-image でパレットとピクセルを同時に編集できます。

- ファイル名の**数値プレフィックスが VRAM 転送順**です。
  後のものが先のものを上書きするため、順序を変えないでください
- `--keep-raw-texture` を付けると変換前の `00000001.BIN` も出力します

### ファイル名の `body` / `shadow` / `tire`
パレットのVRAM行から自動で付く名前です（496 = body、503 = shadow、
504 = tire、それ以外は `clutNNN`）。数値プレフィックスさえ保てば
自由にリネームできます（`clut_presets.json` の `file` も更新してください）。

---

## rcardt-pack

```
C1CircuitTool rcardt-pack -i work/NA8C -o out
C1CircuitTool rcardt-pack -i work/NA8C -o out -p path/to/clut_presets.json
```

編集用フォルダから `.S` を再構築します。フォルダには
`00000000.BIN` と `clut_presets.json`、および JSON が参照する TIM が
揃っている必要があります（無ければエラーで停止します）。

`-p` / `--presets` で別の場所のプリセットファイルを指定できます。

---

## clut_presets.json

パレットのVRAM位置は、モデル側とテクスチャ側で**同じ場所を違う数値で**
指定する必要があります（モデル側は X ÷ 16）。このファイルはその二重指定を
一箇所にまとめるためのもので、`rcardt-pack` と Blenderアドオンが
同じファイルを読みます。

```json
{
  "version": 1,
  "presets": [
    {
      "name": "000_body_256x64",
      "file": "000_body_256x64.TIM",
      "clut_x": 128,
      "clut_y": 496,
      "pixel_x": 640,
      "pixel_y": 0,
      "note": "1 palette(s), 256x64 px 4bpp"
    }
  ]
}
```

- **配列の順序 = VRAM転送順**
- `clut_x` は16の倍数であること（モデル側が ÷16 でしか保持できないため）
- ピクセルの幅・高さは TIM 側から取るため、ps-image で画像サイズを変えても
  このファイルの編集は不要です
- ps-image は VRAM座標を編集できないため、**TIM内の座標は無視され、
  このファイルの値が使われます**

Blender側では、マテリアルの `CLUT Slot` で `name` を選ぶだけで
モデル側に正しい値（`clut_x / 16`, `clut_y`）が書き込まれます。

---

## 検証

市販版ディスクの RCARDT 全17アーカイブについて、以下がバイト単位で一致します。

| 経路 | 結果 |
|---|---|
| `unpack` → QuickBMS の出力と比較 | 34/34 ファイル一致 |
| `unpack` → `pack` → `unpack` | 34/34 ファイル一致 |
| `rcardt-unpack` → `rcardt-pack` → `unpack` | 34/34 ファイル一致 |

---

## ビルド

```
dotnet build C1CircuitTool/C1CircuitTool.csproj -c Release
```

## ファイル構成
```
C1CircuitTool/
├── Program.cs              コマンドライン定義
├── Lzss0.cs                ゲーム互換 LZSS0 デコーダ
├── SFile.cs                .S アーカイブの読み書き
├── Unpacker.cs / Packer.cs 汎用 unpack / pack
└── Rcardt/
    ├── VramBlock.cs        00000001.BIN のブロック
    ├── TimFile.cs          TIM の読み書き
    ├── ClutPresets.cs      clut_presets.json
    ├── RcardtUnpacker.cs
    └── RcardtPacker.cs
```
