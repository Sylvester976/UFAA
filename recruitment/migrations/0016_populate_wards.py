from django.db import migrations


def populate_wards(apps, schema_editor):
    Constituency = apps.get_model('recruitment', 'Constituency')
    Ward         = apps.get_model('recruitment', 'Ward')

    data = {
        # Mombasa
        'Changamwe': ['Port Reitz', 'Kipevu', 'Airport', 'Miritini', 'Chaani'],
        'Jomvu':     ['Jomvu Kuu', 'Magongo', 'Mikindani'],
        'Kisauni':   ['Mjambere', 'Junda', 'Bamburi', 'Mwakirunge', 'Mtopanga', 'Magogoni', 'Shanzu'],
        'Nyali':     ['Frere Town', 'Ziwa La Ng\'ombe', 'Mkomani', 'Kongowea', 'Kadzandani'],
        'Likoni':    ['Mtongwe', 'Shika Adabu', 'Bofu', 'Likoni', 'Timbwani'],
        'Mvita':     ['Mji Wa Kale/Makadara', 'Tudor', 'Tononoka', 'Shimanzi/Ganjoni', 'Majengo'],

        # Kwale
        'Msambweni': ['Gombato Bongwe', 'Ukunda', 'Kinondo', 'Ramisi'],
        'Lungalunga':['Pongwe/Kikoneni', 'Dzombo', 'Mwereni', 'Vanga'],
        'Matuga':    ['Tsimba Golini', 'Waa', 'Tiwi', 'Kubo South', 'Shimba Hills'],
        'Kinango':   ['Ndavaya', 'Puma', 'Kinango', 'Chidini', 'Mackinnon Road', 'Mwavumbo', 'Kasemeni'],

        # Kilifi
        'Kilifi North': ['Tezo', 'Sokoni', 'Kibarani', 'Dabaso', 'Matsangoni', 'Watamu', 'Mnarani'],
        'Kilifi South': ['Junju', 'Bambe', 'Chasimba', 'Mtepeni'],
        'Kaloleni':  ['Mariakani', 'Kayafungo', 'Kaloleni', 'Mwanamwinga'],
        'Rabai':     ['Rabai/Mlarani', 'Ruruma', 'Kambe/Ribe'],
        'Ganze':     ['Ganze', 'Bamba', 'Jaribuni', 'Sokoke'],
        'Malindi':   ['Jilore', 'Kakuyuni', 'Ganda', 'Malindi Town', 'Shella'],
        'Magarini':  ['Marafa', 'Magarini', 'Gongoni', 'Adu', 'Garashi', 'Sabaki'],

        # Tana River
        'Garsen':    ['Garsen South', 'Garsen Central', 'Garsen North', 'Garsen West', 'Kipini East', 'Kipini West'],
        'Galole':    ['Kinakomba', 'Mikinduni', 'Chewani', 'Wayu'],
        'Bura':      ['Bangale', 'Sala', 'Bura', 'Chewele', 'Gone/Binary'],

        # Lamu
        'Lamu East': ['Faza', 'Kiunga', 'Basuba'],
        'Lamu West': ['Shela', 'Mkomani', 'Hindi', 'Mkunumbi', 'Hongwe', 'Witu', 'Bahari'],

        # Taita Taveta
        'Taveta':    ['Chala', 'Mahoo', 'Bomang\'ombe', 'Taveta'],
        'Wundanyi':  ['Wundanyi/Mbale', 'Werugha', 'Wumingu/Kishushe', 'Mwanda/Mgange'],
        'Mwatate':   ['Rong\'e', 'Mwatate', 'Bura', 'Chawia', 'Wusi/Kishamba'],
        'Voi':       ['Mbololo', 'Sagala', 'Kaloleni', 'Marungu', 'Kasigau', 'Ngolia'],

        # Garissa
        'Garissa Township': ['Waberi', 'Galbet', 'Township', 'Waberi', 'Iftin'],
        'Balambala': ['Balambala', 'Danyere', 'Jarajila', 'Lafey', 'Maalimin'],
        'Lagdera':   ['Modogashe', 'Benane', 'Goreale', 'Maalimin', 'Baraki', 'Habaswein'],
        'Dadaab':    ['Dertu', 'Dadaab', 'Lafonsa', 'Liboi', 'Damajale'],
        'Fafi':      ['Bura', 'Dekaharia', 'Jarajila', 'Fafi', 'Nanighi'],
        'Ijara':     ['Ijara', 'Masalani', 'Sangailu', 'Hulugho'],

        # Wajir
        'Wajir North':  ['Gurar', 'Bute', 'Korondille', 'Gheddo', 'Wajir Bor', 'Tarbaj'],
        'Wajir East':   ['Arbajahan', 'Hadado/Athibohol', 'Wagberi', 'Township', 'Barwaqo'],
        'Tarbaj':       ['Tarbaj', 'Wargadud', 'Kutulo', 'Sarman'],
        'Wajir West':   ['Griftu', 'Godoma', 'Munakata', 'Diif'],
        'Eldas':        ['Eldas', 'Della', 'Lakoley South/Basir', 'Lafey'],
        'Wajir South':  ['Elwak North', 'Elwak South', '懒Takaba South', 'Ademasajida', 'Ganyure/Wagalla'],

        # Mandera
        'Mandera West': ['Takaba', 'Takaba South', 'Lagsure', 'Dandu', 'Dertu'],
        'Banissa':      ['Banissa', 'Derkhale', 'Guba', 'Malkamari'],
        'Mandera North':['Ashabito', 'Morothile', 'Lagsure', 'Rhamu', 'Rhamu Dimtu'],
        'Mandera South':['Wargadud', 'Kutulo', 'Elwak North', 'Elwak South', 'Shimbir Fatuma'],
        'Mandera East': ['Khalalio', 'Neboi', 'Township', 'Arabia'],
        'Lafey':        ['Lafey', 'Sala', 'Waretete', 'Libehia'],

        # Marsabit
        'Moyale':    ['Butiye', 'Sololo', 'Heillu/Manyatta', 'Golbo', 'Moyale Township', 'Marsabit'],
        'North Horr':['Illeret', 'North Horr', 'Malabot', 'Turbi', 'Dukana'],
        'Saku':      ['Marsabit Central', 'Sagante/Jaldesa', 'Karare', 'Lontolio'],
        'Laisamis':  ['Logologo', 'Kargi/South Horr', 'Korr/Ngurunit', 'Laisamis'],

        # Isiolo
        'Isiolo North': ['Wabera', 'Bulla Pesa', 'Chari', 'Burat', 'Old Town'],
        'Isiolo South': ['Cherab', 'Ngaremara', 'Kinna', 'Thuuru', 'Garbatulla'],

        # Meru
        'Igembe South':   ['Antubetwe Kiongo', 'Naathu', 'Amwathi'],
        'Igembe Central': ['Akirang\'ondu', 'Athiru Gaiti', 'Igembe East', 'Njia'],
        'Igembe North':   ['Antuambui', 'Ntunene', 'Antubetwe Kilili', 'Akachiu', 'Kanuni'],
        'Tigania West':   ['Athiru Ruujine', 'Atirithia', 'Akithi', 'Kianjai', 'Nkomo'],
        'Tigania East':   ['Mbeu', 'Muthara', 'Karama', 'Nkomo', 'Mitunguu', 'Igwamiti'],
        'North Imenti':   ['Municipality', 'Ntima East', 'Ntima West', 'Nyaki West', 'Nyaki East'],
        'Buuri':          ['Timau', 'Kisima', 'Kiirua/Naari', 'Ruiri/Rwarera'],
        'Central Imenti': ['Mwanganthia', 'Abogeta East', 'Abogeta West', 'Nkuene'],
        'South Imenti':   ['Mitunguu', 'Igoji East', 'Igoji West'],

        # Tharaka Nithi
        'Maara':                ['Magumoni', 'Murugi/Mugumango', 'Mwimbi', 'Ganga', 'Nkuene'],
        'Chuka/Igambang\'ombe': ['Marima', 'Karingari', 'Igambang\'ombe', 'Mugwe', 'Karocho', 'Kibuka', 'Itugururu'],
        'Tharaka':              ['Gatunga', 'Mukothima', 'Nkondi', 'Chiakariga', 'Marimanti'],

        # Embu
        'Manyatta':   ['Kirimari', 'Gaturi South', 'Gaturi North', 'Central', 'Ruguru'],
        'Runyenjes':  ['Kagaari South', 'Central', 'Kagaari North', 'Kyeni North', 'Kyeni South'],
        'Mbeere South':['Mavuria', 'Kiambere', 'Mbeti North', 'Mwea'],
        'Mbeere North':['Nthawa', 'Muminji', 'Evurore'],

        # Kitui
        'Mwingi North':   ['Kyuso', 'Mumoni', 'Tseikuru', 'Tharaka'],
        'Mwingi West':    ['Nguutani', 'Nguni', 'Nuu', 'Mui'],
        'Mwingi Central': ['Mwingi Central', 'Kivou', 'Ngomeni', 'Kyome/Thaana', 'Waita'],
        'Kitui West':     ['Mutonguni', 'Kauwi', 'Matinyani', 'Kwa Mutonga/Kithumula'],
        'Kitui Rural':    ['Kanziku', 'Nguni', 'Kangu', 'Maluma', 'Kisasi', 'Mbitini'],
        'Kitui Central':  ['Miambani', 'Township', 'Kyangwithya West', 'Mulango', 'Kyangwithya East'],
        'Kitui East':     ['Zombe/Mwitika', 'Nzambani', 'Chuluni', 'Voo/Kyamatu', 'Endau/Malalani', 'Mutito/Kaliku'],
        'Kitui South':    ['Ikanga/Kyatune', 'Mutomo', 'Mutha', 'Ikutha', 'Kwa Vonza/Yatta', 'Athi'],

        # Machakos
        'Masinga':    ['Masinga Central', 'Ekalakala', 'Muthesya', 'Ndithini', 'Kivaa'],
        'Yatta':      ['Ndalani', 'Matuu', 'Kithimani', 'Ikombe', 'Katangi'],
        'Kangundo':   ['Kangundo North', 'Kangundo Central', 'Kangundo East', 'Kangundo West'],
        'Matungulu':  ['Tala', 'Matungulu North', 'Matungulu East', 'Matungulu West', 'Kyeleni'],
        'Kathiani':   ['Mitaboni', 'Kathiani Central', 'Upper Kaewa/Iveti', 'Lower Kaewa'],
        'Mavoko':     ['Athi River', 'Kinanie', 'Muthwani', 'Syokimau/Mulolongo'],
        'Machakos Town': ['Mutituni', 'Machakos Central', 'Mua', 'Mutonguni', 'Kalama'],
        'Mwala':      ['Mwala', 'Mbiuni', 'Makutano/Mwala', 'Kibauni', 'Nguluni'],

        # Makueni
        'Mbooni':     ['Tulimani', 'Mbooni', 'Kithungo/Kitundu', 'Kisau/Kiteta'],
        'Kilome':     ['Kasikeu', 'Mukaa', 'Kiima Kimwe/Kalawa'],
        'Kaiti':      ['Kalamba', 'Nguu/Masumba', 'Kee', 'Kilungu', 'Ilima'],
        'Makueni':    ['Wote', 'Muvau/Kikumini', 'Mavindini', 'Kitise/Kithuki'],
        'Kibwezi West':['Makindu', 'Nguumo', 'Kikumbulyu North', 'Kikumbulyu South', 'Nguu/Masumba'],
        'Kibwezi East':['Emali/Mulala', 'Kiangwe', 'Mtito Andei', 'Thange', 'Ivingoni/Nzambani'],

        # Nyandarua
        'Kinangop':   ['Gathara', 'North Kinangop', 'Murungaru', 'Nyakio', 'Engineer'],
        'Kipipiri':   ['Geta', 'Githioro', 'Karau', 'Kipipiri'],
        'Ol Kalou':   ['Karandi', 'Kahuru', 'Ol Kalou', 'Ol Joro Orok', 'Njabini/Kiburu'],
        'Ol Jorok':   ['Gathanji', 'Gatimu', 'Wanjohi', 'Kammwaura', 'Kanjuiri Range'],
        'Ndaragwa':   ['Leshau', 'Pondo', 'Shamata', 'Ndaragwa'],

        # Nyeri
        'Tetu':       ['Dedan Kimathi', 'Wamagana', 'Aguthi-Gaaki'],
        'Kieni':      ['Naromoru Kiamathaga', 'Mwiyogo/Endarasha', 'Mugunda', 'Gatarakwa', 'Thegu River', 'Kabaru', 'Gakawa'],
        'Mathira':    ['Ruguru', 'Kabare', 'Iriaini', 'Konyu', 'Githiru'],
        'Othaya':     ['Mahiga', 'Iria-ini', 'Chinga', 'Karima'],
        'Mukurweini': ['Gikondi', 'Rugi', 'Mukurweini West', 'Mukurweini East'],
        'Nyeri Town': ['Rware', 'Gatitu/Muruguru', 'Kiganjo/Mathari'],

        # Kirinyaga
        'Mwea':           ['Mutithi', 'Kangai', 'Wamsisi', 'Tebere', 'Thiba', 'Nyitibo'],
        'Gichugu':        ['Kabare', 'Baragwi', 'Njukiini', 'Ngariama', 'Karumandi'],
        'Ndia':           ['Mukure', 'Kiine', 'Kariti'],
        'Kirinyaga Central': ['Kerugoya', 'Ciagini', 'Inoi', 'Kagio'],

        # Murang'a
        'Kandara':        ['Ng\'araria', 'Muruka', 'Kariara', 'Ithiru', 'Rwathia'],
        'Gatanga':        ['Ithanga', 'Kakuzi/Mitubiri', 'Mugumo-ini', 'Township', 'Kariara'],
        'Kigumo':         ['Kahumbu', 'Muthithi', 'Kigumo', 'Kangari', 'Kinyona'],
        'Kiharu':         ['Wangu', 'Mukangu', 'Milimani', 'Kiharu', 'Murarandia', 'Gaturi'],
        'Kangema':        ['Kangema', 'Ng\'araria', 'Kanyenya-ini'],
        'Mathioya':       ['Gitugi', 'Kamacharia', 'Kihumbu-ini'],
        'Murang\'a South':['Kimorori/Mwangi', 'Sabasaba', 'Mabounji', 'Gaichanjiru', 'Ithiru'],

        # Kiambu
        'Gatundu South':  ['Kiamwangi', 'Kiganjo', 'Ndarugu', 'Ngenda'],
        'Gatundu North':  ['Gituamba', 'Githobokoni', 'Chania', 'Mang\'u'],
        'Juja':           ['Murera', 'Theta', 'Juja', 'Witeithie', 'Kalimoni'],
        'Thika Town':     ['Kamenu', 'Hospital', 'Gatuanyaga', 'Ngoliba'],
        'Ruiru':          ['Gitothua', 'Biashara', 'Gatongora', 'Kahawa Sukari', 'Kahawa Wendani', 'Kiuu', 'Mwiki', 'Mwihoko'],
        'Githunguri':     ['Githunguri', 'Githiga', 'Ikinu', 'Ngewa', 'Komothai'],
        'Kiambu':         ['Kiambu', 'Murera', 'Township', 'Riabai'],
        'Kiambaa':        ['Cianda', 'Karuri', 'Ndenderu', 'Muchatha', 'Kihara'],
        'Kabete':         ['Gitaru', 'Muguga', 'Nyadhuna', 'Kabete', 'Uthiru'],
        'Kikuyu':         ['Karai', 'Muguga', 'Nachu', 'Sigona', 'Kikuyu'],
        'Limuru':         ['Bibirioni', 'Limuru Central', 'Ndeiya', 'Limuru East', 'Ngecha Tigoni'],
        'Lari':           ['Kijabe', 'Nyanduma', 'Kirenga', 'Lari/Kirenga', 'Kinale'],

        # Turkana
        'Turkana North':  ['Lakezone', 'Lapur', 'Kaeris', 'Kibish', 'Nakalale'],
        'Turkana West':   ['Kakuma', 'Lopur', 'Lokichoggio', 'Nanaam', 'Oropoi', 'Kalobeyei'],
        'Turkana Central':['Kerio Delta', 'Fenchol', 'Lokichar', 'Kainuk', 'Turkwel'],
        'Loima':          ['Loima', 'Turkwel', 'Lorugum', 'Kaputir'],
        'Turkana South':  ['Kalimnyang\'oro', 'Lobei', 'Kapedo/Napeitom', 'Kerio Delta'],
        'Turkana East':   ['Kapedo', 'Katilu', 'Lobokat', 'Kalapata', 'Lokori/Kochodin'],

        # West Pokot
        'Kapenguria':     ['Sook', 'Kapenguria', 'Mnagei', 'Riwo', 'Masool'],
        'Sigor':          ['Masool', 'Labot', 'Tapach', 'Sekerr'],
        'Kacheliba':      ['Kodich', 'Kacheliba', 'Amakuriat', 'Kasei'],
        'Pokot South':    ['Chepareria', 'Batei', 'Lelan', 'Tapach'],

        # Samburu
        'Samburu West':   ['Suguta Marmar', 'Maralal', 'Loosuk', 'Poro', 'El Barta'],
        'Samburu North':  ['Nachola', 'Ndoto', 'Nyiro', 'Bargoi'],
        'Samburu East':   ['Wamba West', 'Wamba East', 'Wamba North', 'Lodokejek'],

        # Trans Nzoia
        'Kwanza':         ['Kwanza', 'Keiyo', 'Bidii', 'Matisi'],
        'Endebess':       ['Endebess', 'Chepchoina', 'Matumbei'],
        'Saboti':         ['Kinyoro', 'Matisi', 'Tuwani', 'Saboti', 'Machewa'],
        'Kiminini':       ['Kiminini', 'Waitaluk', 'St. Teresa', 'Sikhendu', 'Nabiswa'],
        'Cherangany':     ['Sinyerere', 'Kaplamai', 'Motosiet', 'Cherangany/Suwerwa', 'Chepsiro/Kiptoror', 'Sirikwa'],

        # Uasin Gishu
        'Soy':            ['Moi\'s Bridge', 'Kipsomba', 'Soy', 'Kuinet/Kabiyet'],
        'Turbo':          ['Huruma', 'Huruma', 'Ngenyilel', 'Tapsagoi', 'Kamagut', 'Kiplombe', 'Kapsaos', 'Eldoret East'],
        'Moiben':         ['Tembelio', 'Sergoit', 'Karuna/Meibeki', 'Moiben', 'Ainabkoi'],
        'Ainabkoi':       ['Ainabkoi/Olare', 'Kapseret', 'Kesses'],
        'Kapseret':       ['Simat/Kapseret', 'Kipkenyo', 'Ngeria', 'Megun', 'Langas'],
        'Kesses':         ['Tarakwa', 'Megun', 'Tulwet/Chuiyat', 'Ngenyilel'],

        # Elgeyo Marakwet
        'Marakwet East':  ['Embobut/Embulot', 'Endo', 'Sambirir', 'Lelan'],
        'Marakwet West':  ['Moiben', 'Kapyego', 'Sengwer', 'Tot'],
        'Keiyo North':    ['Emsoo', 'Kamariny', 'Kapchemutwa', 'Tosion'],
        'Keiyo South':    ['Arror', 'Metkei', 'Soy North', 'Tangul'],

        # Nandi
        'Tinderet':       ['Tinderet', 'Songhor/Soba', 'Tindiret', 'Chemelil/Chemase'],
        'Aldai':          ['Kabwareng', 'Terik', 'Kemeloi-Maraba', 'Kobujoi', 'Kaptumo-Kaboi', 'Nandi Hills'],
        'Nandi Hills':    ['Nandi Hills', 'Chepkunyuk', 'Ol\'lessos', 'Kapchorua'],
        'Chesumei':       ['Lelmokwo/Ngechek', 'Chemundu/Kapng\'etuny', 'Kosirai', 'Chepkumia'],
        'Emgwen':         ['Kapsabet', 'Ndalat', 'Kilibwoni', 'Chepkoskei'],
        'Mosop':          ['Kipkaren', 'Kurgung/Surungai', 'Kabiyet', 'Ndurio/Ngata', 'Kabisaga'],

        # Baringo
        'Tiaty':          ['Tirioko', 'Kolowa', 'Ribkwo', 'Silale', 'Loiyamorock', 'Tangulbei/Korossi'],
        'Baringo North':  ['Barwessa', 'Kabarnet', 'Saimo/Soi', 'Saimo/Kipsaraman', 'Ewalel/Chapchap', 'Koibatek'],
        'Baringo Central':['Kabimoi', 'Lembus', 'Lembus/Kwen', 'Eldama Ravine', 'Lembus/Perkerra', 'Maji Mazuri'],
        'Baringo South':  ['Marigat', 'Ilchamus', 'Mochongoi', 'Mukutani'],
        'Mogotio':        ['Mogotio', 'Emining', 'Kisanana'],
        'Eldama Ravine':  ['Ravine', 'Mumberes/Maji Mazuri', 'Ng\'enda', 'Koibatek'],

        # Laikipia
        'Laikipia West':  ['Ol-Moran', 'Ndiriti', 'Ngobit', 'Tigithi', 'Thingithu'],
        'Laikipia East':  ['Nanyuki', 'Umande', 'Thingithu', 'Nairutia'],
        'Laikipia North': ['Mukogondo East', 'Mukogondo West'],

        # Nakuru
        'Molo':           ['Molo', 'Turi', 'Marioshoni', 'Elburgon', 'Kuresoi'],
        'Njoro':          ['Njoro', 'Mau Narok', 'Mauche', 'Kihingo', 'Nessuit', 'Lare'],
        'Naivasha':       ['Naivasha East', 'Viwandani', 'Hells Gate', 'Lake View', 'Mai Mahiu', 'Maili Kumi', 'Mirera', 'Naivasha'],
        'Gilgil':         ['Gilgil', 'Mbaruk/Eburu', 'Kariandusi', 'Elementaita'],
        'Kuresoi South':  ['Amalo', 'Keringet', 'Kiptagich', 'Tinet'],
        'Kuresoi North':  ['Kiptororo', 'Nyota', 'Sirikwa', 'Kamara'],
        'Subukia':        ['Subukia', 'Waseges', 'Kabazi'],
        'Rongai':         ['Rongai', 'Menengai West', 'Soin', 'Visoi', 'Mosop', 'Kendege'],
        'Bahati':         ['Bahati', 'Lanet/Umoja', 'Dundori', 'Kabatini', 'Kiamaina', 'Ngata'],
        'Nakuru Town West':['Barut', 'London', 'Kaptembwo', 'Kapkures', 'Rhoda'],
        'Nakuru Town East':['Biashara', 'Kivumbini', 'Flamingo', 'Menengai', 'Nakuru East'],

        # Narok
        'Kilgoris':       ['Kilgoris Central', 'Keyian', 'Angata Barikoi', 'Shankoe', 'Kimintet', 'Ilkisonko'],
        'Emurua Dikirr':  ['Emurua Dikirr', 'Kimintet', 'Ntulele', 'Olpusimoru', 'Olkiriisin'],
        'Narok North':    ['Narok Town', 'Olkeri', 'Ololmasani', 'Mogondo', 'Kapsasian'],
        'Narok East':     ['Mosiro', 'Ildamat', 'Keekonyokie', 'Suswa'],
        'Narok South':    ['Majimoto/Naroosura', 'Ololulung\'a', 'Melelo', 'Loita', 'Sogoo', 'Sagamian'],
        'Narok West':     ['Ilkerin', 'Ololmasani', 'Melelo', 'Loita'],

        # Kajiado
        'Kajiado North':  ['Ngong', 'Olkeri', 'Ongata Rongai', 'Nkoroi'],
        'Kajiado Central':['Purko', 'Ildamat', 'Dalalekutuk', 'Matapato North', 'Matapato South'],
        'Kajiado East':   ['Imaroro', 'Kajiado East', 'Kaputiei North', 'Kitengela', 'Oloosirkon/Sholinke'],
        'Kajiado West':   ['Keekonyokie', 'Iloodokilani', 'Magadi', 'Ewuaso Oonkidong\'i', 'Mosiro'],
        'Kajiado South':  ['Entonet/Lenkisem', 'Loitokitok', 'Rombo', 'Mbirikani/Eselenkei', 'Kimana'],

        # Kericho
        'Kipkelion East': ['Kipkelion', 'Kunyak', 'Chilchila', 'Sorget'],
        'Kipkelion West': ['Londiani', 'Kedowa/Kimulot', 'Chepseon', 'Tendeno/Sorget'],
        'Ainamoi':        ['Ainamoi', 'Kapkugerwet', 'Kisiara', 'Kipchebor', 'Kapletundo'],
        'Bureti':         ['Tebesonik', 'Cheboin', 'Litein', 'Cheplanget', 'Roret'],
        'Belgut':         ['Kabianga', 'Kapsuser', 'Waldai'],
        'Sigowet/Soin':   ['Sigowet', 'Kaplelartet', 'Soliat', 'Soin'],

        # Bomet
        'Sotik':          ['Ndanai/Abosi', 'Chemagel', 'Kipsonoi', 'Mutarakwa', 'Sigor'],
        'Chepalungu':     ['Siongiroi', 'Merigi', 'Kembu', 'Kongasis', 'Ndaraweta', 'Sigor', 'Chesoen'],
        'Bomet East':     ['Chemaner', 'Kipreres', 'Merigi', 'Chemosot', 'Sigor'],
        'Bomet Central':  ['Silibwet Township', 'Ndaraweta', 'Singorwet', 'Chesoen', 'Mutarakwa'],
        'Konoin':         ['Kimulot', 'Mogogosiek', 'Chepchabas', 'Kongasis', 'Embomos'],

        # Kakamega
        'Lugari':         ['Lumakanda', 'Chekalini', 'Chevaywa', 'Lugari', 'Mautuma'],
        'Likuyani':       ['Sango', 'Nzoia', 'Likuyani', 'Kongoni'],
        'Malava':         ['Malava', 'Chemuche', 'Manda-Shivanga', 'Shirere', 'Isukha North', 'Butali/Chegulo'],
        'Lurambi':        ['Butsotso East', 'Butsotso South', 'Butsotso Central', 'Sheywe', 'Mahiakalo', 'Ilesi'],
        'Navakholo':      ['Ingostse-Mathia', 'Shinoyi-Shikomari-Esumeyia', 'Bunyala West', 'Bunyala East', 'Bunyala Central'],
        'Mumias West':    ['Mumias Central', 'Etenje', 'Musanda', 'Makunga', 'Matungu'],
        'Mumias East':    ['Lusheya/Lubinu', 'Malaha/Isongo/Makunga', 'East Wanga'],
        'Matungu':        ['Koyonzo', 'Kholera', 'Chetonyi/Chakol', 'Mayoni', 'Namamali'],
        'Butere':         ['Marama West', 'Marama Central', 'Marama East', 'Marama North', 'Butere'],
        'Khwisero':       ['Kisa East', 'Kisa West', 'Kisa Central', 'Kisa North'],
        'Shinyalu':       ['Idakho South', 'Idakho East', 'Idakho Central', 'Idakho North', 'Isukha South', 'Isukha Central', 'Isukha West'],
        'Ikolomani':      ['Isukha East', 'Isukha North', 'Idakho West'],

        # Vihiga
        'Vihiga':         ['Vihiga', 'Luanda South', 'Tiriki East', 'Wodanga', 'Sabatia'],
        'Sabatia':        ['Chavakali', 'North Maragoli', 'Wodanga', 'Busali'],
        'Hamisi':         ['Shiru', 'Gisambai', 'Shamberere', 'Muhudu', 'Tambua', 'Jepkoyai'],
        'Luanda':         ['Luanda Central', 'Luanda East', 'Luanda South', 'Wemilabi', 'Mwibona', 'Luanda North'],
        'Emuhaya':        ['North East Bunyore', 'Central Bunyore', 'West Bunyore'],

        # Bungoma
        'Mt. Elgon':      ['Cheptais', 'Chesikaki', 'Chepyuk', 'Kapkateny', 'Kaptama', 'Elgon'],
        'Sirisia':        ['Namwela', 'Malakisi/South Kulisiru', 'Lwandanyi'],
        'Kabuchai':       ['Kabuchai/Chwele', 'West Nalondo', 'Bwake/Luuya', 'Mukuyuni'],
        'Bumula':         ['South Bukusu', 'Bumula', 'Khasoko', 'Kabula', 'Kimaeti', 'West Bukusu/Ngoywa', 'Siboti'],
        'Kanduyi':        ['Bukembe West', 'Bukembe East', 'Township', 'Khalaba', 'Musikoma', 'East Sangalo', 'West Sangalo', 'Central Sangalo'],
        'Webuye East':    ['Mihuu', 'Ndivisi', 'Maraka'],
        'Webuye West':    ['Sitikho', 'Matulo', 'Bokoli'],
        'Kimilili':       ['Kimilili', 'Maeni', 'Kamukuywa', 'Kibingei'],
        'Tongaren':       ['Ndalu/Tabani', 'Soysambu/Mitua', 'Naitiri/Kabuyefwe', 'Milima'],

        # Busia
        'Teso North':     ['Malaba Central', 'Malaba North', 'Kings', 'Malaba South'],
        'Teso South':     ['Ang\'urai South', 'Ang\'urai North', 'Ang\'urai East', 'Chakol South', 'Chakol North'],
        'Nambale':        ['Bukhayo North/Walatsi', 'Nambale Township', 'Bukhayo East', 'Bukhayo Central'],
        'Matayos':        ['Marachi East', 'Marachi West', 'Marachi North', 'Marachi Central', 'Kingandole'],
        'Butula':         ['Bunyala North', 'Bunyala Central', 'Bunyala South', 'West Bunyala'],
        'Funyula':        ['Funyula', 'Bulemia', 'Lunyu', 'Sio Port'],
        'Budalangi':      ['Budala', 'Sibuka', 'Bumbe', 'Musoma', 'Budalangi Central', 'Rukala'],

        # Siaya
        'Ugenya':         ['East Ugenya', 'West Ugenya', 'North Ugenya', 'Ukwala'],
        'Ugunja':         ['Ugunja', 'Sigomre', 'Sidindi'],
        'Alego Usonga':   ['Central Alego', 'Siaya Township', 'North Alego', 'South East Alego', 'Usonga', 'West Alego'],
        'Gem':            ['North Gem', 'West Gem', 'Central Gem', 'East Gem', 'Yala Township'],
        'Bondo':          ['Yimbo East', 'Central Sakwa', 'South Sakwa', 'West Sakwa', 'North Sakwa', 'Yimbo West'],
        'Rarieda':        ['East Asembo', 'West Asembo', 'North Uyoma', 'South Uyoma', 'West Uyoma'],

        # Kisumu
        'Kisumu East':    ['Kajulu', 'Kolwa East', 'Manyatta B', 'Nyalenda A', 'Kolwa Central'],
        'Kisumu West':    ['South West Kisumu', 'Central Kisumu', 'Kisumu North', 'West Kisumu', 'North West Kisumu'],
        'Kisumu Central': ['Railways', 'Migosi', 'Shaurimoyo Kaloleni', 'Market Milimani', 'Kondele', 'Nyalenda B'],
        'Seme':           ['Central Seme', 'East Seme', 'West Seme', 'North Seme'],
        'Nyando':         ['Awasi/Onjiko', 'Ahero', 'Kabonyo/Kanyagwal', 'Kobura'],
        'Muhoroni':       ['Muhoroni/Koru', 'Miwani', 'Ombeyi', 'Masogo/Nyang\'oma', 'Chemelil/Chemase'],
        'Nyakach':        ['South West Nyakach', 'North Nyakach', 'Central Nyakach', 'West Nyakach', 'East Nyakach'],

        # Homa Bay
        'Kasipul':        ['West Kasipul', 'Central Kasipul', 'Kasipul South', 'East Kasipul', 'Ruma Kaksingri'],
        'Kabondo Kasipul':['Kabondo East', 'Kokwanyo/Kakelo', 'Kojwach', 'Kabondo West'],
        'Karachuonyo':    ['North Karachuonyo', 'Central Karachuonyo', 'Kanyaluo', 'Kibiri', 'West Karachuonyo', 'Mirogi'],
        'Rangwe':         ['East Rangwe', 'Rangwe', 'Kwabwai', 'Kagan'],
        'Homa Bay Town':  ['Homa Bay Central', 'Homa Bay Arujo', 'Homa Bay East', 'Homa Bay West'],
        'Ndhiwa':         ['Ndhiwa', 'Kwabwai', 'Kanyikela', 'Kabuoch North', 'Kabuoch South/Pala', 'Kagan', 'Kochia'],
        'Suba North':     ['Lambwe', 'Gwassi North', 'Gwassi South', 'Kaksingri West', 'Ruma Kaksingri'],
        'Suba South':     ['Gembe East', 'Gembe West', 'Kaksingri East', 'Mfangano Island', 'Rusinga Island'],

        # Migori
        'Rongo':          ['North Kamagambo', 'Central Kamagambo', 'East Kamagambo', 'South Kamagambo'],
        'Awendo':         ['North Sakwa', 'South Sakwa', 'Central Sakwa', 'West Sakwa', 'Pala'],
        'Suna East':      ['Suna Central', 'Kakrao', 'Kwa', 'Wiga', 'Wasweta II'],
        'Suna West':      ['God Jope', 'Suna Central', 'Wasimbete', 'West Kamagambo'],
        'Uriri':          ['North Kanyamkago', 'Central Kanyamkago', 'East Kanyamkago', 'South Kanyamkago', 'West Kanyamkago'],
        'Nyatike':        ['Kachieng\'', 'Kanyasa', 'North Kadem', 'Macalder/Kanyarwanda', 'Kadem', 'Muhuru'],
        'Kuria West':     ['Masaba', 'Getembe', 'Ntimaru West', 'Ntimaru East', 'Nyabasi East', 'Nyabasi West'],
        'Kuria East':     ['Gokeharaka/Getambwega', 'Ntimaru West', 'Ntimaru East', 'Nyabasi East', 'Nyabasi West'],

        # Kisii
        'Bonchari':       ['Bomariba', 'Bogiakumu', 'Riana', 'Bonchari', 'Taracha'],
        'South Mugirango':['Bokeira', 'Magombo', 'Moticho', 'Getenga', 'Nyansiongo'],
        'Bomachoge Borabu':['Bokianga', 'Isena/Itibo', 'Magwagwa', 'Ekerenyo', 'Metembe'],
        'Bobasi':         ['Bobasi Central', 'Bobasi Boitang\'ang\'a', 'Maburi', 'Bosoti/Sengera', 'Nyacheki', 'Bobasi East', 'Bobasi Chache'],
        'Bomachoge Chache':['Township', 'Boochi/Tendere', 'Boochi/Borabu', 'Rigoma', 'Gachuba', 'Kembu'],
        'Nyaribari Masaba':['Manga', 'Moticho', 'Gesima', 'Nyaribari Masaba'],
        'Nyaribari Chache':['Keumbu', 'Kiamokama', 'Boore', 'Bogiakumu', 'Nyanchwa', 'Essaba'],
        'Kitutu Chache North':['Kegati', 'Mwembe', 'Misambi', 'Nyakoe', 'Nkrumah'],
        'Kitutu Chache South':['Kereri', 'Ichuni', 'Nyatieko'],

        # Nyamira
        'Kitutu Masaba':  ['Rigoma', 'Gachuba', 'Kembu', 'Nyamira Town', 'Bosamaro', 'Bonyamatuta', 'Township'],
        'West Mugirango':  ['Nyamakoroto', 'Bumba', 'Bokianga', 'Metembe', 'Magwagwa'],
        'North Mugirango': ['Ekerenyo', 'Metembe', 'Magwagwa', 'Bokianga', 'Isena/Itibo'],
        'Borabu':          ['Masige West', 'Masige East', 'Bonyamatuta', 'Township', 'Bosamaro'],

        # Nairobi
        'Westlands':       ['Kitisuru', 'Parklands/Highridge', 'Karura', 'Kangemi', 'Mountain View'],
        'Dagoretti North': ['Kilimani', 'Kawangware', 'Gatina', 'Kileleshwa', 'Kabiro'],
        'Dagoretti South': ['Mutu-ini', 'Ngando', 'Riruta', 'Uthiru/Ruthimitu', 'Waithaka'],
        'Langata':         ['Karen', 'Nairobi West', 'Mugumoini', 'South C', 'Nyayo Highrise'],
        'Kibra':           ['Laini Saba', 'Lindi', 'Makina', 'Woodley/Kenyatta Golf Course', 'Sarang\'ombe'],
        'Roysambu':        ['Githurai', 'Kahawa West', 'Zimmerman', 'Roysambu', 'Lucky Summer'],
        'Kasarani':        ['Clay City', 'Mwiki', 'Kasarani', 'Njiru', 'Ruai'],
        'Ruaraka':         ['Babadogo', 'Utalii', 'Mathare North', 'Lucky Summer', 'Korogocho'],
        'Embakasi South':  ['Imara Daima', 'Kwa Njenga', 'Kwa Reuben', 'Pipeline', 'Kware'],
        'Embakasi North':  ['Kariobangi North', 'Dandora Area I', 'Dandora Area II', 'Dandora Area III', 'Dandora Area IV'],
        'Embakasi Central':['Kayole North', 'Kayole Central', 'Kayole South', 'Komarock', 'Matopeni/Spring Valley'],
        'Embakasi East':   ['Upper Savanna', 'Lower Savanna', 'Embakasi', 'Utawala', 'Mihango'],
        'Embakasi West':   ['Umoja I', 'Umoja II', 'Mowlem', 'Kariobangi South'],
        'Makadara':        ['Maringo/Hamza', 'Viwandani', 'Harambee', 'Makongeni'],
        'Kamukunji':       ['Pumwani', 'Eastleigh North', 'Eastleigh South', 'Airbase', 'California'],
        'Starehe':         ['Township', 'Pangani', 'Ziwani/Kariokor', 'Landimawe', 'Nairobi Central'],
        'Mathare':         ['Hospital', 'Mabatini', 'Huruma', 'Ngei', 'Mlango Kubwa', 'Kiamaiko'],
    }

    for constituency_name, wards in data.items():
        try:
            constituency = Constituency.objects.get(name=constituency_name)
            for name in wards:
                Ward.objects.get_or_create(name=name, constituency=constituency)
        except Constituency.DoesNotExist:
            pass


def reverse_wards(apps, schema_editor):
    Ward = apps.get_model('recruitment', 'Ward')
    Ward.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0015_populate_ethnic_groups'),
    ]

    operations = [
        migrations.RunPython(populate_wards, reverse_wards),
    ]