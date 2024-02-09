
if ( window.document.body.id === 'top' ) {
    const topBanner = new Swiper('.swiper.--topBanner', { //名前を変える
        loop: true, //最後→最初に戻るループ再生を有効に
        autoplay: { 
            delay: 3000, //何秒ごとにスライドを動かすか
        },
        speed: 1000, //表示切り替えのスピード
        effect: "slide", //切り替えのmotion (※1)
        centeredSlides: true, //中央寄せ
        pagination: {
            el: ".swiper-pagination.--topBanner", //paginationのclass
            clickable: true, //クリックでの切り替えを有効に
            type: "bullet" //paginationのタイプ (※2)
        },
        navigation: {
            prevEl: ".swiper-button-prev.--topBanner", //戻るボタンのclass
            nextEl: ".swiper-button-next.--topBanner" //進むボタンのclass
        },
        allowTouchMove: true, // スワイプで表示の切り替えを無効に
        breakpoints: { //画面幅による表示枚数と余白の指定
            320: {
                slidesPerView: 1,
                spaceBetween: 10,
            },
            375: {
                slidesPerView: 1.4,
                spaceBetween: 14,
            },
            750: {
                slidesPerView: 2.5,
                spaceBetween: 25,
            },
            1025: {
                slidesPerView: 3,
                spaceBetween: 30,
            },
            1300: {
                slidesPerView: 3.4,
                spaceBetween: 30,
            },
            1500: {
                slidesPerView: 3.8,
                spaceBetween: 40,
            },
        }
    });
    
    /* =================================================== 
    ※1 effectについて
    slide：左から次のスライドが流れてくる
    fade：次のスライドがふわっと表示
    ■ fadeの場合は下記を記述
        fadeEffect: {
            crossFade: true
        },
    cube：スライドが立方体になり、3D回転を繰り返す
    coverflow：写真やアルバムジャケットをめくるようなアニメーション
    flip：平面が回転するようなアニメーション
    cards：カードを順番にみていくようなアニメーション
    creative：カスタマイズしたアニメーションを使うときに使用します
    
    =======================================================
    ※2 paginationのタイプ
    bullet：スライド枚数と同じ数のドットが表示
    fraction：分数で表示（例：1 / 3）
    progressbar：スライドの進捗に応じてプログレスバーが伸びる
    custom：自由にカスタマイズ
    
    =====================================================*/
}