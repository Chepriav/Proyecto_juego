package screens 
{
	import starling.display.Button;
	import starling.display.Image;
	import starling.events.Event;
	import starling.display.Sprite;
	import starling.textures.Texture;
	import com.greensock.TweenLite;
	
	/**
	 * ...
	 * @author 
	 */
	public class Welcome extends Sprite 
	{
		private var bg:Image;
		private var title:Image;
		private var hero:Image;
		private var playBtn:Button;
		private var aboutBtn:Button;
		
		public function Welcome() 
		{
			super();
			this.addEventListener(starling.events.Event.ADDED_TO_STAGE, onAddedToStage);
		}
		private function onAddedToStage(event:Event):void
		{
			trace("Welcome screen initialized")
			drawScreen();
		}
		public function drawScreen ():void
		{
			bg = new Image(Assets.getTexture("BgWelcome"));
			this.addChild(bg);
			
			title = new Image(Assets.getTexture("WelcomeTitle"));
			title.x = 440; 
			title.y = 20;
			this.addChild(title);
			
			hero = new Image(Assets.getTexture("WelcomeHero"));
			this.addChild(hero);
			
			playBtn = new Button(Assets.getTexture("WelcomePlayBtn"));
			playBtn.x = 500;
			playBtn.y = 260;
			this.addChild (playBtn);
			
			aboutBtn = new Button (Assets.getTexture("WelcomeAboutBtn"));
			aboutBtn.x = 410;
			aboutBtn.y = 380;
			this.addChild(aboutBtn);
		
		}
		public function initialize():void
		{
			this.visible = true;
			hero.x = - hero.width;
			hero.y = 100;
			TweenLite.to(hero, 2, {x:80})
			this.addEventListener(Event.ENTER_FRAME, heroAnimation);
		}
		
		private function heroAnimation(e:Event):void 
		{
			var currentDate:Date = new Date();
				hero.y = 100 + (Math.cos(currentDate.getTime() * 0.002) * 25);
				
				playBtn.x = 500 + (Math.cos(currentDate.getTime() * 0.002) * 10);
				playBtn.y = 260 + (Math.sin(currentDate.getTime() * 0.002) * 10);
				
				aboutBtn.x = 410 + (Math.cos(currentDate.getTime() * 0.003) * 10);
				aboutBtn.y = 380 + (Math.sin(currentDate.getTime() * 0.003) * -10);
				
		}
	}

}