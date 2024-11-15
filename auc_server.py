#CSC573: Internet Protcols
#Contributers: Sakshi Basapure(sbasapu) and Pankhi Saini(psaini2)
#Date: Oct 17, 2024

import socket
import threading
import time
import sys

# Server information
SERVER = '0.0.0.0'

# Global variables to manage the auction state
auction_status = 0  # 0 = Waiting for Seller, 1 = Waiting for Buyers
seller_info = {}  # Auction request from the seller
buyers = []       # List to store buyer connections
bids = []
seller_data = {}
seller_connected = False
clients = {}

# Handle Seller client connection
import socket

def handle_seller(client, addr):
    global seller_data, auction_status, seller_connected  # Global variables for auction state
    
    try:
        while True:
            try:
                # Send a message to the client indicating the seller role
                client.send("seller".encode())
                
                # Attempt to receive data from the client
                data = client.recv(1024)
                
                # If no data is received, assume the client disconnected
                if not data:
                    break
                
                # Process the data received
                data = data.decode().strip()
                request = data.split()
                
                # Validate the request length
                if len(request) != 4:
                    client.send("Server: Invalid auction request!".encode())
                    continue
                
                # Attempt to parse the request parameters
                try:
                    auction_type = int(request[0])
                    lowest_price = int(request[1])
                    number_of_bids = int(request[2])
                    item_name = request[3]
                except ValueError:
                    client.send("Invalid input! Ensure that auction_type, lowest_price, and number_of_bids are integers.".encode())
                    continue
                
                # Validate auction parameters
                if (auction_type not in [1, 2] or 
                    lowest_price < 0 or 
                    number_of_bids < 0 or 
                    number_of_bids >= 10 or 
                    len(item_name) > 255):
                    client.send("Server: Invalid auction request!".encode())
                    continue

                # Update seller_data with valid auction request
                seller_data.update({
                    "auction_type": auction_type,
                    "lowest_price": lowest_price,
                    "number_of_bids": number_of_bids,
                    "item_name": item_name,
                    "seller_IP": addr[0]
                })
                
                auction_status = 1  # Set auction status to waiting for buyers
                print(f"Auction request received from {addr}. Now waiting for Buyers.")
                client.send("Server: Auction Start.".encode())
                seller_connected = False  # Reset seller connection flag
                
            except OSError:
                # Ignore OSError and continue silently
                pass

    finally:
        # Ensure the socket is closed properly
        if client:
            client.close()


def handle_buyer(client, addr):
    global buyers, number_of_bids

    client.send("buyer".encode())  # Inform the client it's a buyer

    # Case a: If the current number of buyers is smaller than <number_of_bids>
    if len(buyers) < seller_data["number_of_bids"]:
        buyers.append(client)
        print(f"Buyer {len(buyers)} is connected from {addr}")

        # Notify the client that the server is waiting for more buyers
        if len(buyers) < seller_data["number_of_bids"]:
            client.send("The Auctioneer is still waiting for other Buyer to connect...".encode())
        elif len(buyers) == seller_data["number_of_bids"]:
            spawn_bidding_thread()  # Start the bidding process in a new thread
            # Case b: If the number of buyers reaches <number_of_bids>
            for buyer in buyers:
                buyer.send("The bidding has started!".encode())  # Notify all buyers that bidding is starting

            # Function to handle bids submission
            handle_bid_submission(buyers)

    # Case c: If the number of buyers exceeds <number_of_bids>
    else:
        client.send("Bidding on-going!".encode())  # Inform the new client that bidding is ongoing
        client.close()  # Close the connection for this new client once we notify bidding starts

def handle_bid_submission(buyers):
    bids_received = {}  # Dictionary to store bids from buyers
    
    # Collect bids from buyers
    for index, buyer in enumerate(buyers):  # Use enumerate to get both index and buyer
        while True:
            try:
                # Listen for input from the buyer
                bid_message = buyer.recv(1024).decode().strip()  # Receive bid from each buyer
                
                # Check if the message is a positive integer
                if bid_message.isdigit() and int(bid_message) > 0:
                    bid = int(bid_message)
                    bids_received[buyer] = bid  # Record the bid with the sending Buyer
                    buyer.send("Server: Bid received. Please wait...".encode())  # Notify the Buyer
                    
                    # Print the bid along with the Buyer number
                    print(f"Buyer {index + 1} bid: ${bid}")  # Corrected to show the buyer number
                    break  # Exit the loop to stop receiving further messages from this Buyer
                else:
                    buyer.send("Server: Invalid bid. Please submit a positive integer!".encode())  # Invalid input
            except Exception as e:
                print(f"Error receiving bid: {e}")
                buyer.close()  # Close the connection if there's an error
                break  # Exit the loop in case of error
    
    # Process the bids after receiving them
    process_bids(bids_received)

def process_bids(bids_received):
    global seller_data  # Access the global seller_data dictionary
    
    # Initialize highest and second highest bids and buyers
    highest_bid = 0
    second_highest_bid = 0
    winning_buyer = None
    second_highest_buyer = None
    
    # Sort bids and identify the highest and second highest bids
    sorted_bids = sorted(bids_received.items(), key=lambda item: item[1], reverse=True)

    # Assign the highest and second highest bids if they exist
    if len(sorted_bids) > 0:
        winning_buyer, highest_bid = sorted_bids[0]  # Highest bid and winning buyer
    if len(sorted_bids) > 1:
        second_highest_buyer, second_highest_bid = sorted_bids[1]  # Second highest bid and second highest buyer

    # Check if the auction succeeds based on the highest bid and lowest price
    lowest_price = seller_data.get("lowest_price")
    
    if highest_bid >= lowest_price:
        # Auction succeeds
        auction_type = seller_data.get("auction_type")  # Get auction type
        
        if auction_type == 1:  # First-price auction
            actual_payment = highest_bid
            print(f"Item sold! The highest bid is {highest_bid}. The actual payment is {actual_payment}.")
        elif auction_type == 2:  # Second-price auction
            actual_payment = second_highest_bid
            print(f"Item sold! The highest bid is {highest_bid}. The actual payment is {actual_payment}.")
        
        item_name = seller_data.get("item_name")
        sellerIP = seller_data.get("seller_IP")
        winnerIP = winning_buyer.getpeername()[0]

        #Notify the seller
        notify_seller(item_name, actual_payment,winnerIP)
        # Notify the winning buyer
        item_name = seller_data.get("item_name")
        notify_winner(winning_buyer, item_name, actual_payment,sellerIP)

        # Notify losing buyers
        losing_buyers = [buyer for buyer in bids_received.keys() if buyer != winning_buyer]
        notify_losers(losing_buyers)

        # Close all buyer connections
        for buyer in bids_received.keys():
            buyer.close()

        # Close seller's connection
        seller_socket = seller_info['client']
        # seller_socket.close()

        reset_auction()

    else:
        print("Auction failed. The highest bid does not meet the lowest price requirement.")

def notify_winner(winning_buyer, item_name, actual_payment,sellerIP):
    # Send notification to the winning buyer
    message = (
        f"Auction finished!\n"
        f"You won this item: {item_name}!\n"
        f"Your payment due is {actual_payment}.\n"
        f"Disconnecting from the Auctioneer server.\n"
        f"Auction is over!"
    )
    winning_buyer.send(message.encode())
    winning_buyer.send(sellerIP.encode())

def notify_losers(losing_buyers):
    # Notify all losing buyers that the auction has ended and they did not win
    for buyer in losing_buyers:
        message = (
            f"Auction finished!\n"
            f"Unfortunately, you did not win in the last round.\n"
            f"Disconnecting from the Auctioneer server. Auction is over!"
        )
        buyer.sendall(message.encode())

def notify_seller(item_name, highest_bid,winnerIP):
    # Send notification to the seller with auction details
    message = (
        f"Auction finished!\n"
        f"Success! Your item {item_name} has been sold for {highest_bid}.\n"
        f"Disconnecting from the Auctioneer server. Auction is over!"
    )
    
    # Get the seller's client socket from seller_info
    seller_socket = seller_info['client']
    
    # Send the message to the seller using the socket
    seller_socket.sendall(message.encode())
    seller_socket.send(winnerIP.encode())

# Function to start the bidding thread
def spawn_bidding_thread():
    print(">> Bidding Thread spawned")
    bidding_thread = threading.Thread(target=start_bidding)
    bidding_thread.start()

# Placeholder function to start the actual bidding process
def start_bidding():
    print("Requested number of bidders arrived. Let's start bidding!")
    pass

# Reset the auction state
def reset_auction():
    global seller_data, bids, auction_status, seller_info, buyers
    seller_data = {}
    bids = []
    auction_status = 0
    seller_info = {}
    buyers = []


# Main server function
def start_server(port):
    global auction_status, seller_info, seller_connected

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SERVER, port))
    server.listen(6)

    print(f"Auctioneer is ready for hosting auctions!")

    while True:
        client, addr = server.accept()

        if auction_status == 0 and not seller_info:
            # Client is first, so it should be the seller
            seller_info["client"] = client
            print(f"Seller is connected from {addr}")
            seller_connected = True  # Mark that seller has connected
            seller_thread = threading.Thread(target=handle_seller, args=(client, addr))
            # Start the seller thread
            seller_thread.start()
            print(">> New Seller Thread spawned")

        elif auction_status == 0 and seller_connected:
            # Before the seller submits the auction request, send "Server busy!" and close the connection
            client.send("Server is busy. Try to connect again later.".encode())
            client.close()

        else:
            # Handle buyer clients once seller has submitted the auction request
            if auction_status == 1:
                buyer_thread = threading.Thread(target=handle_buyer, args=(client, addr))
                # Start the buyer thread
                buyer_thread.start()

if __name__ == "__main__":
    # Check if the port number is provided
    if len(sys.argv) != 2:
        print("Usage: python auc_server.py <portnumber>")
        sys.exit(1)

    # Directly convert the port number from the command line argument
    port_number = int(sys.argv[1])

    start_server(port_number)