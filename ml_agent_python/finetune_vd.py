import os
import shutil
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from tqdm import tqdm
import time

# Import the model architecture
from model import VoiceDetector

def main():
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {DEVICE}")

    # 1. Load the balanced dataset
    if not os.path.exists("training_data.pt"):
        print("Error: training_data.pt not found. Run prepare_dataset.py first.")
        return

    print("Loading training_data.pt...")
    data = torch.load("training_data.pt")
    X = data["X"] # Raw audio (N, 48000)
    y = data["y"].unsqueeze(1) # (N, 1)

    print(f"Dataset shape: {X.shape}")
    
    dataset = TensorDataset(X, y)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    # 2. Load the pre-trained model
    model_path = os.path.join("models", "best_voice_detector.pth")
    backup_path = os.path.join("models", "best_voice_detector_backup.pth")
    
    if os.path.exists(model_path):
        print(f"Backing up original weights to {backup_path}")
        shutil.copy2(model_path, backup_path)
    
    model = VoiceDetector().to(DEVICE)
    if os.path.exists(model_path):
        print("Loading pre-trained weights...")
        model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    else:
        print("No existing weights found. Training from scratch!")

    # 3. Setup training parameters
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    EPOCHS = 15
    
    print("\nStarting Fine-Tuning...")
    
    model.train()
    
    for epoch in range(EPOCHS):
        running_loss = 0.0
        correct = 0
        total = 0
        
        # tqdm progress bar for the epoch
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{EPOCHS}", leave=False)
        
        for batch_X, batch_y in pbar:
            batch_X = batch_X.to(DEVICE)
            batch_y = batch_y.to(DEVICE)
            
            optimizer.zero_grad()
            
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * batch_X.size(0)
            
            # Calculate accuracy
            preds = torch.sigmoid(outputs) >= 0.5
            correct += (preds == batch_y).sum().item()
            total += batch_y.size(0)
            
            pbar.set_postfix({"Loss": f"{loss.item():.4f}", "Acc": f"{(correct/total)*100:.1f}%"})
            
        epoch_loss = running_loss / total
        epoch_acc = (correct / total) * 100
        print(f"Epoch {epoch+1}/{EPOCHS} - Loss: {epoch_loss:.4f} - Acc: {epoch_acc:.1f}%")

    # 4. Save the fine-tuned model
    print(f"\nSaving fine-tuned weights to {model_path}...")
    torch.save(model.state_dict(), model_path)
    print("Done! The model is ready for the presentation!")

if __name__ == "__main__":
    main()
