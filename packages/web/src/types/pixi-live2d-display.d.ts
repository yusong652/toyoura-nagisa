declare module 'pixi-live2d-display' {
  import * as PIXI from 'pixi.js';
  
  export class Live2DModel extends PIXI.Container {
    static from(modelPath: string): Promise<Live2DModel>;
    static registerTicker(ticker: any): void;
    
    internalModel: any;
    parameters: any;
    
    motion(group: string): Promise<any>;
  }
} 