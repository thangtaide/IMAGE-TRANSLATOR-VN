"""Neutral tight-frame fixtures; no OCR inference, provider or private artwork."""
import copy

import numpy as np
import pytest
from PIL import Image,ImageDraw

from core.imaging import TextRenderer,TextLayoutError
from core.types import Options
from tests.test_readability import region


TEXT='Gửi email để nhận địa chỉ trang web hôm nay'


def renderer():
    return TextRenderer(Options(font_min=10,font_max=16))


def check(renderer,image,regions,texts,protected=()):
    before=image.tobytes();source=copy.deepcopy(regions)
    output=renderer.render(image,regions,texts,protected_regions=protected)
    plans=renderer.last_layout
    assert image.tobytes()==before and regions==source
    assert sorted(i for p in plans for i in p['region_indices']+p['duplicate_indices'])==list(range(len(regions)))
    for i,p in enumerate(plans):
        assert p['wrapped'].split()==p['text'].split()
        assert 10<=p['font_size']<=16
        a,b,c,d=p['paint_box'];x,y,z,t=p['box']
        assert 0<=x<=a<c<=z<=image.width and 0<=y<=b<d<=t<=image.height
        for other in plans[i+1:]:assert not renderer._intersects(p['paint_box'],other['paint_box'])
        for protected_region in protected:assert not renderer._intersects(p['paint_box'],protected_region.box)
    changed=np.any(np.array(output)!=np.array(image),axis=2)
    allowed=np.zeros(changed.shape,dtype=bool)
    for p in plans:
        x0,y0,x1,y1=p['box'];allowed[y0:y1,x0:x1]=True
    assert not np.any(changed & ~allowed)
    return output,plans


def test_179x23_top_label_expands_upward_avoiding_next_line():
    r=renderer();regions=[region((1095,9,1274,32)),region((1102,33,1264,56),'mail@example.test')]
    with pytest.raises(TextLayoutError):r.plan_layout((1280,720),regions,[TEXT,'mail@example.test'])
    _,plans=check(r,Image.new('RGB',(1280,720),'black'),regions,[TEXT,'mail@example.test'])
    assert plans[0]['layout_strategy']=='local-flat-background-wrap'
    assert plans[0]['source_box']==[1095,9,1274,32]
    assert not r._intersects(plans[0]['box'],plans[1]['box'])


def test_word_wrap_two_or_three_lines_inside_closed_bubble():
    image=Image.new('RGB',(400,260),'white')
    ImageDraw.Draw(image).rectangle((90,75,290,190),outline='black',width=3)
    r=TextRenderer(Options(font_min=10,font_max=12))
    text='Những người bạn vẫn luôn ở đây để cùng nhau vượt qua mọi khó khăn.'
    output=r.render(image,[region((100,110,279,133))],[text]);plan=r.last_layout[0]
    assert plan['wrapped'].split()==text.split() and 2<=len(plan['wrapped'].splitlines())<=3
    x0,y0,x1,y1=plan['box'];assert 93<=x0<x1<=288 and 78<=y0<y1<=188
    assert output.size==image.size


@pytest.mark.parametrize('box',[(0,70,179,93),(181,70,360,93),(90,0,269,23),(90,137,269,160)])
def test_expansion_near_each_image_edge_stays_in_bounds(box):
    r=renderer();_,plans=check(r,Image.new('RGB',(360,160),'black'),[region(box)],[TEXT])
    assert plans[0]['layout_strategy']=='local-flat-background-wrap'


def test_nearby_labels_reserve_each_others_frames():
    r=renderer();regions=[region((100,30,279,53)),region((100,54,279,77),'second')]
    _,plans=check(r,Image.new('RGB',(420,180),'white'),regions,[TEXT,TEXT+' nhé'])
    assert len(plans)==2 and not r._intersects(plans[0]['box'],plans[1]['box'])


def test_protected_numeric_area_is_not_available_for_expansion():
    r=renderer();protected=[region((80,55,310,75),'12345')]
    _,plans=check(r,Image.new('RGB',(400,180),'black'),[region((110,80,289,103))],[TEXT],protected)
    assert not r._intersects(plans[0]['box'],protected[0].box)


def test_texture_uses_explicit_background_overlap_fallback():
    pixels=(np.indices((120,300)).sum(axis=0)%2*255).astype('uint8')
    image=Image.fromarray(pixels).convert('RGB');r=renderer()
    _,plans=check(r,image,[region((50,40,229,63))],[TEXT])
    assert plans[0]['layout_strategy']=='background-overlap-wrap'


@pytest.mark.parametrize('box',[(0,0,64,30),(336,0,400,30),(0,150,64,180),(336,150,400,180)])
def test_small_merged_label_can_overlap_art_at_all_corners(box):
    pixels=(np.indices((180,400)).sum(axis=0)%2*255).astype('uint8')
    image=Image.fromarray(pixels).convert('RGB');r=renderer()
    x,y,_,_=box
    regions=[region((x,y,x+60,y+17),'label'),region((x,y+11,x+64,y+30),'web')]
    _,plans=check(r,image,regions,['Tùy Tính ACG','a41415.com'])
    assert len(plans)==1 and plans[0]['region_indices']==[0,1]
    assert plans[0]['layout_strategy']=='background-overlap-wrap'
    assert plans[0]['box']!=list(box)


def test_background_expansion_can_exceed_old_local_limits():
    pixels=(np.indices((180,700)).sum(axis=0)%2*255).astype('uint8')
    r=renderer();text='a41415.'+'com'*15
    _,plans=check(r,Image.fromarray(pixels).convert('RGB'),[region((10,10,74,40))],[text])
    assert plans[0]['box'][2]-plans[0]['box'][0]>64+2*26
    assert plans[0]['layout_strategy']=='background-overlap-wrap'


def test_background_overlap_still_respects_protected_text_and_no_room():
    image=Image.new('RGB',(200,100),'black');r=renderer()
    protected=[region((64,0,200,100),'keep'),region((0,30,64,100),'123')]
    with pytest.raises(TextLayoutError):r.render(image,[region((0,0,64,30))],[TEXT],protected_regions=protected)
    assert r.last_layout==[]


def test_no_room_falls_back_before_any_text_is_drawn(monkeypatch):
    image=Image.new('RGB',(50,25),'white');before=image.tobytes();r=renderer();calls=[]
    monkeypatch.setattr(ImageDraw.ImageDraw,'multiline_text',lambda *a,**k:calls.append(1))
    with pytest.raises(TextLayoutError):r.render(image,[region((0,0,40,23))],[TEXT*10])
    assert not calls and r.last_layout==[] and image.tobytes()==before


def test_transparent_surroundings_cannot_supply_invisible_extra_space():
    image=Image.new('RGBA',(400,180),(255,255,255,0))
    ImageDraw.Draw(image).rectangle((110,80,288,102),fill=(255,255,255,255))
    with pytest.raises(TextLayoutError):renderer().render(image,[region((110,80,289,103))],[TEXT])


def test_valid_existing_layout_is_identical_with_or_without_pixels():
    r=renderer();regions=[region((10,10,290,70)),region((10,90,290,150),'second')]
    texts=['Chữ Việt có dấu: ă â đ ê ô ơ ư','Giữ nguyên vị trí cũ.']
    expected=r.plan_layout((320,180),regions,texts)
    _,actual=check(r,Image.new('RGB',(320,180),'white'),regions,texts)
    assert actual==expected and all('layout_strategy' not in p for p in actual)


def test_unbroken_word_is_never_cut_to_force_a_fit():
    with pytest.raises(TextLayoutError):renderer().render(Image.new('RGB',(120,80),'white'),
        [region((20,20,80,43))],['Từ_không_được_cắt_'*30])


def test_duplicate_ocr_does_not_block_its_own_safe_expansion():
    first=region((1095,9,1274,32));r=renderer()
    _,plans=check(r,Image.new('RGB',(1280,720),'black'),[first,copy.deepcopy(first)],[TEXT,TEXT])
    assert len(plans)==1 and plans[0]['duplicate_indices']==[1]


def test_pipeline_passes_preserved_numeric_regions_to_renderer(tmp_path,monkeypatch):
    from core.pipeline import ProcessingManager,TranslationService,JobControl
    from core.storage import TranslationCache
    from tests.test_core import FakeOCR,FakeProvider
    source=tmp_path/'input';source.mkdir();Image.new('RGB',(400,180),'white').save(source/'1.png')
    opts=Options(source=str(source),output=str(tmp_path/'output'),language='en')
    text=region((20,30,150,70),'Hello');text.language='en'
    number=region((160,30,250,70),'123');number.language='en'
    seen=[];original=TextRenderer.render
    def capture(self,image,regions,texts,**kwargs):
        seen.extend(kwargs['protected_regions']);return original(self,image,regions,texts,**kwargs)
    monkeypatch.setattr(TextRenderer,'render',capture)
    monkeypatch.setattr('core.pipeline.erase_text',lambda image,*args:image.copy())
    cache=TranslationCache(tmp_path/'state.sqlite3');control=JobControl()
    try:
        service=TranslationService(opts,cache,control,offline=FakeProvider())
        result=ProcessingManager(opts,cache=cache,control=control,service=service,ocr=FakeOCR([text,number])).run()
        assert result['completed']==1 and [r.text for r in seen]==['123']
    finally:cache.close()
