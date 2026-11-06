from app.services import detected_content_language, generated_content_uses_language

AZ='''Qeydiyyatdan əvvəl saytın şərtlərini diqqətlə oxuyun və hesabın təhlükəsizliyini yoxlayın. Ödəniş üçün seçilən üsulun qaydaları haqqında məlumat əldə etmək vacibdir. Şəxsi məlumatları yalnız təsdiq edilmiş səhifədə daxil edin. İstifadə zamanı məbləğ və vaxt hədləri müəyyən etmək lazımdır. Oyunçular bonus şərtlərini başa düşmədən mərc etməməlidir. Həmçinin əlaqə məlumatlarını yoxlayın və dəstək xidməti ilə danışın. Bu seçim hər kəs üçün uyğun deyil və risklər haqqında düşünmək lazımdır.'''
TR='''Kayıt işleminden önce sitenin koşullarını dikkatlice okuyun ve hesabınızın güvenliğini kontrol edin. Ödeme yöntemi için belirtilen kuralları öğrenmek önemlidir. Kişisel bilgilerinizi yalnızca doğrulanmış sayfalarda paylaşın. Kullanım sırasında para ve zaman sınırları belirlemek gerekir. Oyuncular bonus koşullarını anlamadan bahis yapmamalıdır. İletişim bilgilerini inceleyin ve destek hizmetiyle görüşün. Bu seçenek herkes için uygun değildir ve olası riskleri değerlendirmek gerekir.'''
def payload(text):return {'pages':[{'content':{'blocks':[{'type':'paragraph','data':{'text':text}}]}}]}

def test_azerbaijani_is_recognized_with_all_project_locale_spellings():
    value=payload(AZ+' '+AZ)
    assert detected_content_language(value)=='az'
    assert generated_content_uses_language(value,'az_AZ')
    assert generated_content_uses_language(value,'az-AZ')
    assert not generated_content_uses_language(value,'tr')

def test_turkish_is_still_rejected_for_azerbaijani_projects():
    assert detected_content_language(payload(TR+' '+TR))=='tr'
    assert not generated_content_uses_language(payload(TR+' '+TR),'az')

def test_a_short_azerbaijani_quote_does_not_accept_a_turkish_article():
    value=payload(TR*8+' '+AZ)
    assert not generated_content_uses_language(value,'az')
