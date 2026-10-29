const int led1 = 6;
const int led2 = 5;
const int led3 = 4;
const int bouton = 2;

int compteur = 0;
int etatPrecedent = HIGH;

void setup() {
  // put your setup code here, to run once:
pinMode(led1,OUTPUT);
pinMode(led2,OUTPUT);
pinMode(led3,OUTPUT);
pinMode(bouton,INPUT_PULLUP);
}

void loop() {
  // put your main code here, to run repeatedly:
int etatBouton = digitalRead(bouton);
if (etatPrecedent==HIGH && etatBouton==LOW){
  compteur = (compteur+1)%4;
  delay(50);
}
etatPrecedent=etatBouton;
digitalWrite(led1,compteur>=1);
digitalWrite(led2,compteur>=2);
digitalWrite(led3,compteur>=3);
}