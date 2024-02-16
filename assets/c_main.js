
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

    const topVoices = new Swiper('.swiper.--topVoices', { //名前を変える
        loop: true, //最後→最初に戻るループ再生を有効に
        speed: 1000, //表示切り替えのスピード
        effect: "slide", //切り替えのmotion (※1)
        //centeredSlides: true, //中央寄せ
        navigation: {
            prevEl: ".swiper-button-prev.--topVoices", //戻るボタンのclass
            nextEl: ".swiper-button-next.--topVoices" //進むボタンのclass
        },
        allowTouchMove: true, // スワイプで表示の切り替えを無効に
        slidesPerView: 1, // 一度に表示する枚数
        spaceBetween: 30,
    });

    const topPicture = new Swiper('.swiper.--topPicture', { //名前を変える
        loop: true, //最後→最初に戻るループ再生を有効に
        autoplay: { 
            delay: 0, //何秒ごとにスライドを動かすか
        },
        speed: 5000, //表示切り替えのスピード
        effect: "slide", //切り替えのmotion (※1)
        centeredSlides: true, //中央寄せ
        allowTouchMove: true, // スワイプで表示の切り替えを無効に
        slidesPerView: "auto",
        spaceBetween: 0,
    });
}



jQuery(function($) {
    $('.c_header__item a').on('click', function () {
        $('.c_header__subMenu').removeClass('js-open');
        $($(this).attr('href')).addClass('js-open');
        $('.c_header__subMenu--bg').addClass('js-open');
        $('body').addClass('no-scroll');
        return false;
    });

    $('.c_header__subMenu--bg').on('click', function () {
        $('.c_header__subMenu').removeClass('js-open');
        $(this).removeClass('js-open');
        $('body').removeClass('no-scroll');
        return false;
    });

    $('.c_drawer__icon').on('click', function () {
        
        return false;
    });
});

